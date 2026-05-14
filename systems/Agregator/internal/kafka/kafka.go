package kafka

import (
	"context"
	"crypto/tls"
	"encoding/json"
	"log"
	"os"

	"github.com/kirilltahmazidi/aggregator/internal/config"
	"github.com/kirilltahmazidi/aggregator/internal/gateway"
	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/store"
	kafkago "github.com/segmentio/kafka-go"
	"github.com/segmentio/kafka-go/sasl/plain"
)

// Service инкапсулирует kafka reader/writer и запускает цикл обработки.
type Service struct {
	reader         *kafkago.Reader
	writer         *kafkago.Writer // пишет responses обратно (для других сервисов)
	outWriter      *kafkago.Writer // пишет задания эксплуатантам в operator.requests
	operatorReader *kafkago.Reader // читает ответы эксплуатантов из operator.responses
	dlt            *kafkago.Writer // dead-letter topic для нечитаемых сообщений
	gateway        *gateway.Gateway
	store          *store.Store // для обновления статусов заказов
}

func NewService(cfg *config.Config, g *gateway.Gateway, s *store.Store) *Service {
	dialer := newDialer()
	transport := newTransport(dialer)

	// читает из aggregator.requests
	reader := kafkago.NewReader(kafkago.ReaderConfig{
		Brokers:  []string{cfg.KafkaBroker},
		Topic:    cfg.RequestTopic,  //откуда читаем
		GroupID:  cfg.ConsumerGroup, // имя группы
		Dialer:   dialer,
		MinBytes: 1,
		MaxBytes: 10e6, // 10 MB
		Logger:   kafkago.LoggerFunc(func(msg string, args ...interface{}) { log.Printf("[kafka/reader] "+msg, args...) }),
	})

	// пишет в aggregator.responses
	writer := &kafkago.Writer{
		Addr:      kafkago.TCP(cfg.KafkaBroker),
		Topic:     cfg.ResponseTopic, //куда пишем
		Balancer:  &kafkago.LeastBytes{},
		Logger:    kafkago.LoggerFunc(func(msg string, args ...interface{}) { log.Printf("[kafka/writer] "+msg, args...) }),
		Transport: transport,
	}

	// пишет задания эксплуатантам в operator.requests
	outWriter := &kafkago.Writer{
		Addr:      kafkago.TCP(cfg.KafkaBroker),
		Topic:     cfg.OperatorTopic,
		Balancer:  &kafkago.LeastBytes{},
		Logger:    kafkago.LoggerFunc(func(msg string, args ...interface{}) { log.Printf("[kafka/out] "+msg, args...) }),
		Transport: transport,
	}

	// это кароче если пришел мусор который нельзя прочитать => кладем в отдельный топик
	dlt := &kafkago.Writer{
		Addr:      kafkago.TCP(cfg.KafkaBroker),
		Topic:     cfg.DeadLetterTopic,
		Balancer:  &kafkago.LeastBytes{},
		Transport: transport,
	}

	// читает ответы эксплуатантов: оферты цен и результаты выполнения
	operatorReader := kafkago.NewReader(kafkago.ReaderConfig{
		Brokers:  []string{cfg.KafkaBroker},
		Topic:    cfg.OperatorResponseTopic,
		GroupID:  cfg.ConsumerGroup + "-operator-resp",
		Dialer:   dialer,
		MinBytes: 1,
		MaxBytes: 10e6,
		Logger:   kafkago.LoggerFunc(func(msg string, args ...interface{}) { log.Printf("[kafka/operator-reader] "+msg, args...) }),
	})

	return &Service{
		reader:         reader,
		writer:         writer,
		outWriter:      outWriter,
		operatorReader: operatorReader,
		dlt:            dlt,
		gateway:        g,
		store:          s,
	}
}

func newDialer() *kafkago.Dialer {
	dialer := &kafkago.Dialer{}

	username := os.Getenv("BROKER_USER")
	password := os.Getenv("BROKER_PASSWORD")
	if username == "" && password == "" {
		return dialer
	}

	dialer.SASLMechanism = plain.Mechanism{
		Username: username,
		Password: password,
	}

	if os.Getenv("KAFKA_TLS_ENABLED") == "true" {
		dialer.TLS = &tls.Config{
			MinVersion: tls.VersionTLS12,
		}
	}

	return dialer
}

func newTransport(dialer *kafkago.Dialer) *kafkago.Transport {
	transport := &kafkago.Transport{}
	if dialer == nil {
		return transport
	}

	transport.TLS = dialer.TLS
	transport.SASL = dialer.SASLMechanism
	return transport
}

// PublishOrder отправляет заказ в топик operator.requests — эксплуатанты его читают.
// Вызывается из HTTP-обработчика когда фронт создаёт заказ.
func (s *Service) PublishOrder(ctx context.Context, order *store.Order) error {
	// собираем payload в формате models.CreateOrderRequest
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

	// оборачиваем в стандартный конверт Request — чтобы формат совпадал с остальными сообщениями
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

	err = s.outWriter.WriteMessages(ctx, kafkago.Message{
		Key:   []byte(order.ID), // ключ = ID заказа, Kafka использует его для партиционирования
		Value: data,
	})
	if err != nil {
		return err
	}

	log.Printf("[kafka] order published to operators order_id=%s", order.ID)
	return nil
}

// PublishConfirmPrice отправляет эксплуатанту подтверждение цены от пользователя.
// Вызывается из HTTP-обработчика POST /orders/{id}/confirm-price.
func (s *Service) PublishConfirmPrice(ctx context.Context, payload models.ConfirmPricePayload) error {
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

	err = s.outWriter.WriteMessages(ctx, kafkago.Message{
		Key:   []byte(payload.OrderID),
		Value: msgBytes,
	})
	if err != nil {
		return err
	}

	log.Printf("[kafka] price confirmed to operator order_id=%s operator_id=%s price=%.2f",
		payload.OrderID, payload.OperatorID, payload.AcceptedPrice)
	return nil
}

// RunOperatorConsumer читает из operator.responses — сюда эксплуатанты пишут оферты цен и результаты.
// Запускается параллельно с Run в main.go.
func (s *Service) RunOperatorConsumer(ctx context.Context) error {
	log.Printf("[kafka] starting operator response consumer topic=%s", s.operatorReader.Config().Topic)
	defer s.operatorReader.Close()

	for {
		select {
		case <-ctx.Done():
			log.Println("[kafka] operator consumer: context cancelled")
			return ctx.Err()
		default:
		}

		msg, err := s.operatorReader.ReadMessage(ctx)
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			log.Printf("[kafka] operator consumer read error: %v", err)
			continue
		}

		log.Printf("[kafka] operator message offset=%d type_hint=key:%s", msg.Offset, string(msg.Key))
		s.processOperatorMessage(ctx, msg)
	}
}

func (s *Service) processOperatorMessage(_ context.Context, msg kafkago.Message) {
	var req models.Request
	if err := json.Unmarshal(msg.Value, &req); err != nil {
		log.Printf("[kafka] operator consumer: cannot unmarshal message: %v", err)
		return
	}

	switch req.Action {
	case models.MsgPriceOffer:
		var p models.PriceOfferPayload
		if err := json.Unmarshal(req.Payload, &p); err != nil {
			log.Printf("[kafka] price_offer: invalid payload: %v", err)
			return
		}
		if s.store.SetOperatorOffer(p.OrderID, p.OperatorID, p.Price) {
			log.Printf("[kafka] price_offer stored order_id=%s operator=%s price=%.2f",
				p.OrderID, p.OperatorID, p.Price)
		} else {
			log.Printf("[kafka] price_offer: order not found order_id=%s", p.OrderID)
		}

	case models.MsgOrderResult:
		var p models.OrderResultPayload
		if err := json.Unmarshal(req.Payload, &p); err != nil {
			log.Printf("[kafka] order_result: invalid payload: %v", err)
			return
		}
		if s.store.ProcessOrderResult(p.OrderID, p.Success) {
			log.Printf("[kafka] order_result applied order_id=%s success=%v", p.OrderID, p.Success)
		} else {
			log.Printf("[kafka] order_result: ignored or not found order_id=%s (invalid state transition)", p.OrderID)
		}

	default:
		log.Printf("[kafka] operator consumer: unknown action=%s", req.Action)
	}
}

func (s *Service) Run(ctx context.Context) error {
	log.Printf("[kafka] starting consumer loop on topic=%s", s.reader.Config().Topic)
	defer s.reader.Close()
	defer s.writer.Close()
	defer s.outWriter.Close()
	defer s.dlt.Close()

	for {
		select {
		case <-ctx.Done():
			log.Println("[kafka] context cancelled, shutting down consumer")
			return ctx.Err()
		default:
		}

		msg, err := s.reader.ReadMessage(ctx) // ждем сообщение
		if err != nil {
			if ctx.Err() != nil {
				return ctx.Err()
			}
			log.Printf("[kafka] read error: %v", err)
			continue
		}

		log.Printf("[kafka] received message offset=%d partition=%d key=%s",
			msg.Offset, msg.Partition, string(msg.Key))

		s.processMessage(ctx, msg) // обрабатываем
	}
}

func (s *Service) processMessage(ctx context.Context, msg kafkago.Message) {
	var req models.Request
	if err := json.Unmarshal(msg.Value, &req); err != nil {
		log.Printf("[kafka] cannot unmarshal message: %v — sending to DLT", err)
		s.sendToDLT(ctx, msg)
		return
	}

	resp := s.gateway.Route(req)

	respBytes, err := json.Marshal(resp)
	if err != nil {
		log.Printf("[kafka] cannot marshal response for correlation_id=%s: %v", req.GetCorrelationID(), err)
		return
	}

	correlationID := req.GetCorrelationID()
	if correlationID == "" {
		correlationID = string(msg.Key)
	}

	out := kafkago.Message{
		Key:   []byte(correlationID),
		Value: respBytes,
	}

	if err := s.writer.WriteMessages(ctx, out); err != nil {
		log.Printf("[kafka] failed to write response for correlation_id=%s: %v", correlationID, err)
	} else {
		log.Printf("[kafka] response sent for correlation_id=%s success=%v", correlationID, resp.Success)
	}

	// Обновляем статус заказа в store — фронт увидит изменение через GET /orders/{id}
	if req.Action == models.MsgCreateOrder && resp.Success {
		if s.store.UpdateOrderStatus(correlationID, store.StatusSearching) {
			log.Printf("[kafka] order status updated to searching order_id=%s", correlationID)
		}
	}
}

func (s *Service) sendToDLT(ctx context.Context, original kafkago.Message) {
	if err := s.dlt.WriteMessages(ctx, kafkago.Message{
		Key:   original.Key,
		Value: original.Value,
	}); err != nil {
		log.Printf("[kafka] failed to write to DLT: %v", err)
	}
}
