package mqtt

import (
	"context"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	paho "github.com/eclipse/paho.mqtt.golang"

	"github.com/kirilltahmazidi/aggregator/internal/config"
	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/store"
)

// Сервис публикует и потребляет сообщения через MQTT параллельно с Kafka
type Service struct {
	client paho.Client
	cfg    *config.Config
	store  *store.Store
}

// NewService подключается к MQTT брокеру и возвращает готовый сервис
func NewService(cfg *config.Config, s *store.Store) (*Service, error) {
	opts := paho.NewClientOptions()

	broker := cfg.MQTTBroker
	if broker == "" {
		broker = "mqtt:1883"
	}
	if !strings.HasPrefix(broker, "tcp://") && !strings.HasPrefix(broker, "ssl://") && !strings.HasPrefix(broker, "ws://") {
		broker = "tcp://" + broker
	}
	opts.AddBroker(broker)

	if cfg.MQTTClientID != "" {
		opts.SetClientID(cfg.MQTTClientID)
	}
	if cfg.MQTTUsername != "" {
		opts.SetUsername(cfg.MQTTUsername)
		opts.SetPassword(cfg.MQTTPassword)
	}

	opts.SetKeepAlive(30 * time.Second)
	opts.SetPingTimeout(10 * time.Second)
	opts.SetConnectRetry(true)
	opts.SetAutoReconnect(true)

	client := paho.NewClient(opts)
	if token := client.Connect(); token.Wait() && token.Error() != nil {
		return nil, fmt.Errorf("mqtt connect: %w", token.Error())
	}

	return &Service{client: client, cfg: cfg, store: s}, nil
}

// PublishOrder отправляет (дублирует) данные create_order в MQTT топик operator.requests
func (s *Service) PublishOrder(_ context.Context, order *store.Order) error {
	payload, err := json.Marshal(models.CreateOrderRequest{
		CustomerID:     order.CustomerID,
		Description:    order.Description,
		Budget:         order.Budget,
		FromLat:        order.FromLat,
		FromLon:        order.FromLon,
		ToLat:          order.ToLat,
		ToLon:          order.ToLon,
		MissionType:    order.MissionType,
		SecurityGoals:  order.SecurityGoals,
		TopLeftLat:     order.TopLeftLat,
		TopLeftLon:     order.TopLeftLon,
		BottomRightLat: order.BottomRightLat,
		BottomRightLon: order.BottomRightLon,
	})
	if err != nil {
		return err
	}

	req := models.Request{
		Action:        models.MsgCreateOrder,
		Payload:       payload,
		Sender:        models.DefaultSender,
		CorrelationID: order.ID,
	}
	data, err := json.Marshal(req)
	if err != nil {
		return err
	}

	token := s.client.Publish(s.cfg.MQTTOperatorTopic, s.cfg.MQTTQoS, false, data)
	token.Wait()
	if token.Error() != nil {
		return token.Error()
	}
	log.Printf("[mqtt] order published order_id=%s", order.ID)
	return nil
}

// PublishConfirmPrice отправляет (дублирует) данные confirm_price в MQTT топик operator.requests
func (s *Service) PublishConfirmPrice(_ context.Context, payload models.ConfirmPricePayload) error {
	data, err := json.Marshal(payload)
	if err != nil {
		return err
	}
	req := models.Request{
		Action:        models.MsgConfirmPrice,
		Payload:       json.RawMessage(data),
		Sender:        models.DefaultSender,
		CorrelationID: payload.OrderID,
	}
	msgBytes, err := json.Marshal(req)
	if err != nil {
		return err
	}

	token := s.client.Publish(s.cfg.MQTTOperatorTopic, s.cfg.MQTTQoS, false, msgBytes)
	token.Wait()
	if token.Error() != nil {
		return token.Error()
	}
	log.Printf("[mqtt] price confirmed order_id=%s operator_id=%s", payload.OrderID, payload.OperatorID)
	return nil
}

// RunOperatorConsumer слушает ответы операторов через MQTT и применяет их к хранилищу (store)
func (s *Service) RunOperatorConsumer(ctx context.Context) error {
	messageCh := make(chan paho.Message, 16)
	cb := func(_ paho.Client, m paho.Message) { messageCh <- m }

	if token := s.client.Subscribe(s.cfg.MQTTOperatorRespTopic, s.cfg.MQTTQoS, cb); token.Wait() && token.Error() != nil {
		return fmt.Errorf("mqtt subscribe: %w", token.Error())
	}
	log.Printf("[mqtt] subscribed to operator responses topic=%s", s.cfg.MQTTOperatorRespTopic)

	for {
		select {
		case <-ctx.Done():
			return ctx.Err()
		case msg := <-messageCh:
			s.processOperatorMessage(msg.Payload())
		}
	}
}

func (s *Service) processOperatorMessage(data []byte) {
	var req models.Request
	if err := json.Unmarshal(data, &req); err != nil {
		log.Printf("[mqtt] operator message unmarshal error: %v", err)
		return
	}

	switch req.Action {
	case models.MsgPriceOffer:
		var p models.PriceOfferPayload
		if err := json.Unmarshal(req.Payload, &p); err != nil {
			log.Printf("[mqtt] price_offer invalid payload: %v", err)
			return
		}
		if s.store.SetOperatorOffer(p.OrderID, p.OperatorID, p.Price) {
			log.Printf("[mqtt] price_offer stored order_id=%s operator=%s price=%.2f", p.OrderID, p.OperatorID, p.Price)
		} else {
			log.Printf("[mqtt] price_offer: order not found order_id=%s", p.OrderID)
		}
	case models.MsgOrderResult:
		var p models.OrderResultPayload
		if err := json.Unmarshal(req.Payload, &p); err != nil {
			log.Printf("[mqtt] order_result invalid payload: %v", err)
			return
		}
		if s.store.ProcessOrderResult(p.OrderID, p.Success) {
			log.Printf("[mqtt] order_result applied order_id=%s success=%v", p.OrderID, p.Success)
		} else {
			log.Printf("[mqtt] order_result: ignored or not found order_id=%s (invalid state transition)", p.OrderID)
		}
	default:
		// игнорируем неизвестные типы сообщений
	}
}
