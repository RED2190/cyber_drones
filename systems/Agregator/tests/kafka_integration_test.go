package tests

import (
	"context"
	"encoding/json"
	"fmt"
	"math"
	"net"
	"net/http"
	"os"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/segmentio/kafka-go"
)

const (
	defaultKafkaReadTimeout = 120 * time.Second
	defaultDialTimeout      = 2 * time.Second
)

type kafkaEnvelope struct {
	Action        string          `json:"action"`
	RequestID     string          `json:"request_id,omitempty"`
	CorrelationID string          `json:"correlation_id,omitempty"`
	Type          string          `json:"type,omitempty"`
	Status        string          `json:"status,omitempty"`
	Payload       json.RawMessage `json:"payload,omitempty"`
	Success       bool            `json:"success"`
	Error         string          `json:"error,omitempty"`
}

type kafkaFixture struct {
	brokers               []string
	requestTopic          string
	responseTopic         string
	dltTopic              string
	operatorTopic         string
	operatorResponseTopic string
}

var kafkaWarmupOnce sync.Once
var kafkaTestReaderGroupID = uniqueID("tests-kafka-reader")

func TestKafkaCreateOrderRequestResponse(t *testing.T) {
	fx := newKafkaFixture(t)
	requestID := uniqueID("kafka-create-order")

	response := fx.sendRequestAndReadResponse(t, requestID, "create_order", map[string]any{
		"customer_id":    uniqueID("customer"),
		"description":    "Доставить документы из офиса на склад",
		"budget":         3200.5,
		"mission_type":   "delivery",
		"security_goals": []string{"ЦБ1", "ЦБ3"},
		"from_lat":       55.7558,
		"from_lon":       37.6173,
		"to_lat":         55.8,
		"to_lon":         37.65,
	})

	if response.RequestID != requestID {
		if response.CorrelationID != requestID {
			t.Fatalf("unexpected correlation id in response: got request_id=%q correlation_id=%q, want %q", response.RequestID, response.CorrelationID, requestID)
		}
	}
	if response.Action != "response" {
		t.Fatalf("unexpected action in response: got %q", response.Action)
	}
	if !response.Success {
		t.Fatalf("unexpected unsuccessful response: error=%q", response.Error)
	}

	var payload struct {
		OrderID string `json:"order_id"`
		Status  string `json:"status"`
		Message string `json:"message"`
	}
	mustUnmarshalJSON(t, response.Payload, &payload)

	if strings.TrimSpace(payload.OrderID) == "" {
		t.Fatal("response payload.order_id should not be empty")
	}
	if payload.Status != "pending" {
		t.Fatalf("unexpected payload.status: got %q, want %q", payload.Status, "pending")
	}
	if strings.TrimSpace(payload.Message) == "" {
		t.Fatal("response payload.message should not be empty")
	}
}

func TestKafkaUnknownMessageTypeReturnsError(t *testing.T) {
	fx := newKafkaFixture(t)
	requestID := uniqueID("kafka-unknown-type")

	response := fx.sendRequestAndReadResponse(t, requestID, "totally_unknown_type", map[string]any{
		"sample": true,
	})

	if response.RequestID != requestID && response.CorrelationID != requestID {
		t.Fatalf("unexpected correlation id in response: got request_id=%q correlation_id=%q, want %q", response.RequestID, response.CorrelationID, requestID)
	}
	if response.Action != "response" {
		t.Fatalf("unexpected action in response: got %q", response.Action)
	}
	if response.Success {
		t.Fatalf("unexpected success for unknown message type")
	}
	if !strings.Contains(response.Error, "unknown action") {
		t.Fatalf("unexpected error message: %q", response.Error)
	}
}

func TestKafkaMalformedMessageGoesToDLT(t *testing.T) {
	fx := newKafkaFixture(t)
	messageKey := uniqueID("kafka-dlt")
	malformed := []byte(`{"request_id":"broken","type":"create_order","payload":`)

	fx.writeRawMessage(t, fx.requestTopic, messageKey, malformed)

	readCtx, cancelRead := context.WithTimeout(context.Background(), defaultKafkaReadTimeout)
	defer cancelRead()

	dlt := fx.readRawFromTopic(t, readCtx, fx.dltTopic, func(msg kafka.Message) bool {
		return string(msg.Key) == messageKey
	})

	if string(dlt.Key) != messageKey {
		t.Fatalf("unexpected DLT message key: got %q, want %q", string(dlt.Key), messageKey)
	}
	if string(dlt.Value) != string(malformed) {
		t.Fatalf("unexpected DLT payload: got %q, want %q", string(dlt.Value), string(malformed))
	}
}

func TestKafkaOperatorResponsesUpdateOrderLifecycle(t *testing.T) {
	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	operatorID := uniqueID("operator")
	offerPrice := 2780.75

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "price_offer", map[string]any{
		"order_id":               orderID,
		"operator_id":            operatorID,
		"operator_name":          "Kafka Operator",
		"price":                  offerPrice,
		"estimated_time_minutes": 25,
	})

	matched := waitForOrderStatus(t, baseURL, orderID, "matched", customer.Token)
	if matched.OperatorID != operatorID {
		t.Fatalf("unexpected operator_id after price_offer: got %q, want %q", matched.OperatorID, operatorID)
	}
	if math.Abs(matched.OfferedPrice-offerPrice) > 0.0001 {
		t.Fatalf("unexpected offered_price after price_offer: got %v, want %v", matched.OfferedPrice, offerPrice)
	}

	confirmPriceResp := doJSONRequestWithAuth(t, "POST", baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    operatorID,
		"accepted_price": offerPrice,
	}, customer.Token)
	defer confirmPriceResp.Body.Close()
	if confirmPriceResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for confirm-price request: %d", confirmPriceResp.StatusCode)
	}

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "order_result", map[string]any{
		"order_id":    orderID,
		"operator_id": operatorID,
		"success":     true,
		"reason":      "",
	})

	completedPending := waitForOrderStatus(t, baseURL, orderID, "completed_pending_confirmation", customer.Token)
	if completedPending.ID != orderID {
		t.Fatalf("unexpected order id after order_result: got %q, want %q", completedPending.ID, orderID)
	}
}

func TestKafkaConfirmCompletionFinalizesOrder(t *testing.T) {
	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	operatorID := uniqueID("operator-complete")

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "price_offer", map[string]any{
		"order_id":               orderID,
		"operator_id":            operatorID,
		"operator_name":          "Completion Operator",
		"price":                  1900.0,
		"estimated_time_minutes": 20,
	})
	_ = waitForOrderStatus(t, baseURL, orderID, "matched", customer.Token)

	confirmPriceResp := doJSONRequestWithAuth(t, "POST", baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    operatorID,
		"accepted_price": 1900.0,
	}, customer.Token)
	defer confirmPriceResp.Body.Close()
	if confirmPriceResp.StatusCode != 200 {
		t.Fatalf("unexpected status for confirm-price request: %d", confirmPriceResp.StatusCode)
	}

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "order_result", map[string]any{
		"order_id":    orderID,
		"operator_id": operatorID,
		"success":     true,
		"reason":      "",
	})

	_ = waitForOrderStatus(t, baseURL, orderID, "completed_pending_confirmation", customer.Token)

	confirmCompletionResp := doJSONRequestWithAuth(t, "POST", baseURL+"/orders/"+orderID+"/confirm-completion", map[string]any{}, customer.Token)
	defer confirmCompletionResp.Body.Close()
	if confirmCompletionResp.StatusCode != 200 {
		t.Fatalf("unexpected status for confirm-completion request: %d", confirmCompletionResp.StatusCode)
	}

	var completionBody struct {
		OrderID string `json:"order_id"`
		Status  string `json:"status"`
	}
	decodeJSON(t, confirmCompletionResp.Body, &completionBody)
	if completionBody.OrderID != orderID {
		t.Fatalf("unexpected order_id in confirm-completion response: got %q, want %q", completionBody.OrderID, orderID)
	}
	if completionBody.Status != "completed" {
		t.Fatalf("unexpected status in confirm-completion response: got %q", completionBody.Status)
	}

	completed := waitForOrderStatus(t, baseURL, orderID, "completed", customer.Token)
	if completed.ID != orderID {
		t.Fatalf("unexpected order id after confirm-completion: got %q, want %q", completed.ID, orderID)
	}
}

func TestKafkaOrderResultFailureSetsDispute(t *testing.T) {
	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	operatorID := uniqueID("operator-dispute")

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "price_offer", map[string]any{
		"order_id":               orderID,
		"operator_id":            operatorID,
		"operator_name":          "Dispute Operator",
		"price":                  2100.0,
		"estimated_time_minutes": 30,
	})
	_ = waitForOrderStatus(t, baseURL, orderID, "matched", customer.Token)

	confirmPriceResp := doJSONRequestWithAuth(t, "POST", baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    operatorID,
		"accepted_price": 2100.0,
	}, customer.Token)
	defer confirmPriceResp.Body.Close()
	if confirmPriceResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for confirm-price request: %d", confirmPriceResp.StatusCode)
	}

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "order_result", map[string]any{
		"order_id":    orderID,
		"operator_id": operatorID,
		"success":     false,
		"reason":      "delivery failed",
	})

	dispute := waitForOrderStatus(t, baseURL, orderID, "dispute", customer.Token)
	if dispute.ID != orderID {
		t.Fatalf("unexpected order id after failed order_result: got %q, want %q", dispute.ID, orderID)
	}
}

func TestKafkaCreateOrderUpdatesStatusToSearching(t *testing.T) {
	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	// Повторно отправляем create_order в aggregator.requests с request_id равным существующему заказу,
	// чтобы проверить, что Kafka consumer переводит заказ в статус searching.
	response := fx.sendRequestAndReadResponse(t, orderID, "create_order", map[string]any{
		"customer_id":    uniqueID("customer-for-searching"),
		"description":    "Доставить документы из офиса на склад",
		"budget":         1800.0,
		"mission_type":   "delivery",
		"security_goals": []string{"ЦБ1"},
		"from_lat":       55.75,
		"from_lon":       37.61,
		"to_lat":         55.8,
		"to_lon":         37.65,
	})

	if !response.Success {
		t.Fatalf("unexpected unsuccessful response: %q", response.Error)
	}

	searching := waitForOrderStatus(t, baseURL, orderID, "searching", customer.Token)
	if searching.ID != orderID {
		t.Fatalf("unexpected order id after searching update: got %q, want %q", searching.ID, orderID)
	}
}

func TestKafkaHTTPFlowPublishesOperatorRequests(t *testing.T) {
	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)

	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	operatorID := uniqueID("operator-confirm")
	acceptedPrice := 2100.0

	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "price_offer", map[string]any{
		"order_id":               orderID,
		"operator_id":            operatorID,
		"operator_name":          "Request Publisher Operator",
		"price":                  acceptedPrice,
		"estimated_time_minutes": 25,
	})
	_ = waitForOrderStatus(t, baseURL, orderID, "matched", customer.Token)

	createOrderMsg := fx.readEnvelopeFromTopic(t, fx.operatorTopic, func(msg kafkaEnvelope) bool {
		return (msg.RequestID == orderID || msg.CorrelationID == orderID) && msg.Action == "create_order"
	})

	var createPayload struct {
		CustomerID  string  `json:"customer_id"`
		Description string  `json:"description"`
		Budget      float64 `json:"budget"`
	}
	mustUnmarshalJSON(t, createOrderMsg.Payload, &createPayload)
	if strings.TrimSpace(createPayload.CustomerID) == "" {
		t.Fatal("operator.requests create_order payload.customer_id should not be empty")
	}
	if strings.TrimSpace(createPayload.Description) == "" {
		t.Fatal("operator.requests create_order payload.description should not be empty")
	}
	if createPayload.Budget <= 0 {
		t.Fatalf("operator.requests create_order payload.budget should be positive, got %v", createPayload.Budget)
	}

	confirmResp := doJSONRequestWithAuth(t, "POST", baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    operatorID,
		"accepted_price": acceptedPrice,
	}, customer.Token)
	defer confirmResp.Body.Close()
	if confirmResp.StatusCode != 200 {
		t.Fatalf("unexpected status for confirm-price request: %d", confirmResp.StatusCode)
	}

	confirmMsg := fx.readEnvelopeFromTopic(t, fx.operatorTopic, func(msg kafkaEnvelope) bool {
		return (msg.RequestID == orderID || msg.CorrelationID == orderID) && msg.Action == "confirm_price"
	})

	var confirmPayload struct {
		OrderID       string  `json:"order_id"`
		OperatorID    string  `json:"operator_id"`
		AcceptedPrice float64 `json:"accepted_price"`
	}
	mustUnmarshalJSON(t, confirmMsg.Payload, &confirmPayload)
	if confirmPayload.OrderID != orderID {
		t.Fatalf("unexpected confirm payload order_id: got %q, want %q", confirmPayload.OrderID, orderID)
	}
	if confirmPayload.OperatorID != operatorID {
		t.Fatalf("unexpected confirm payload operator_id: got %q, want %q", confirmPayload.OperatorID, operatorID)
	}
	if math.Abs(confirmPayload.AcceptedPrice-acceptedPrice) > 0.0001 {
		t.Fatalf("unexpected confirm payload accepted_price: got %v, want %v", confirmPayload.AcceptedPrice, acceptedPrice)
	}
}

func newKafkaFixture(t *testing.T) kafkaFixture {
	t.Helper()

	brokers := resolveKafkaBrokers()
	topics := resolveKafkaTopics()

	waitForKafkaReady(t, brokers)

	fx := kafkaFixture{
		brokers:               brokers,
		requestTopic:          topics.request,
		responseTopic:         topics.response,
		dltTopic:              topics.dlt,
		operatorTopic:         topics.operator,
		operatorResponseTopic: topics.operatorResponse,
	}

	// Health-check не гарантирует, что Kafka consumer уже вступил в consumer group.
	// Делаем one-time warm-up через реальный request/response round-trip.
	kafkaWarmupOnce.Do(func() {
		_ = mustResolveBaseURL(t)
		_ = fx.sendRequestAndReadResponse(t, uniqueID("kafka-warmup"), "totally_unknown_type", map[string]any{
			"warmup": true,
		})
	})

	return fx
}

func (f kafkaFixture) sendRequestAndReadResponse(t *testing.T, requestID, msgType string, payload any) kafkaEnvelope {
	t.Helper()

	f.sendEnvelope(t, f.requestTopic, requestID, msgType, payload)
	return f.readEnvelopeFromTopic(t, f.responseTopic, func(msg kafkaEnvelope) bool {
		return msg.RequestID == requestID || msg.CorrelationID == requestID
	})
}

func (f kafkaFixture) sendEnvelope(t *testing.T, topic, requestID, msgType string, payload any) {
	t.Helper()

	envelope := map[string]any{
		"request_id": requestID,
		"type":       msgType,
		"payload":    payload,
	}
	data, err := json.Marshal(envelope)
	if err != nil {
		t.Fatalf("failed to marshal kafka envelope: %v", err)
	}

	f.writeRawMessage(t, topic, requestID, data)
}

func (f kafkaFixture) writeRawMessage(t *testing.T, topic, key string, payload []byte) {
	t.Helper()

	writer := &kafka.Writer{
		Addr:         kafka.TCP(f.brokers...),
		Topic:        topic,
		Balancer:     &kafka.LeastBytes{},
		RequiredAcks: kafka.RequireAll,
	}
	defer func() {
		if err := writer.Close(); err != nil {
			t.Fatalf("failed to close kafka writer: %v", err)
		}
	}()

	writeCtx, cancelWrite := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancelWrite()

	err := writer.WriteMessages(writeCtx, kafka.Message{Key: []byte(key), Value: payload})
	if err != nil {
		t.Fatalf("failed to write kafka message to topic %q: %v", topic, err)
	}
}

func (f kafkaFixture) readEnvelopeFromTopic(t *testing.T, topic string, matches func(kafkaEnvelope) bool) kafkaEnvelope {
	t.Helper()

	readCtx, cancelRead := context.WithTimeout(context.Background(), defaultKafkaReadTimeout)
	defer cancelRead()

	msg := f.readRawFromTopic(t, readCtx, topic, func(raw kafka.Message) bool {
		var envelope kafkaEnvelope
		if err := json.Unmarshal(raw.Value, &envelope); err != nil {
			return false
		}
		return matches(envelope)
	})

	var envelope kafkaEnvelope
	mustUnmarshalJSON(t, msg.Value, &envelope)
	return envelope
}

func (f kafkaFixture) readRawFromTopic(t *testing.T, readCtx context.Context, topic string, matches func(kafka.Message) bool) kafka.Message {
	t.Helper()

	reader := kafka.NewReader(kafka.ReaderConfig{
		Brokers:     f.brokers,
		Topic:       topic,
		GroupID:     kafkaTestReaderGroupID,
		MinBytes:    1,
		MaxBytes:    10e6,
		StartOffset: kafka.FirstOffset,
	})
	defer func() {
		if err := reader.Close(); err != nil {
			t.Fatalf("failed to close kafka reader: %v", err)
		}
	}()

	for {
		msg, err := reader.ReadMessage(readCtx)
		if err != nil {
			t.Fatalf("failed to read kafka message from topic %q: %v", topic, err)
		}
		if matches(msg) {
			return msg
		}
	}
}

type kafkaTopics struct {
	request          string
	response         string
	dlt              string
	operator         string
	operatorResponse string
}

func resolveKafkaBrokers() []string {
	if fromEnv := strings.TrimSpace(os.Getenv("KAFKA_BROKERS")); fromEnv != "" {
		parts := strings.Split(fromEnv, ",")
		brokers := make([]string, 0, len(parts))
		for _, p := range parts {
			candidate := strings.TrimSpace(p)
			if candidate != "" {
				brokers = append(brokers, candidate)
			}
		}
		if len(brokers) > 0 {
			return brokers
		}
	}

	if broker := strings.TrimSpace(os.Getenv("KAFKA_BROKER")); broker != "" {
		return []string{broker}
	}

	return []string{"kafka:9092", "localhost:29092", "localhost:9092"}
}

func resolveKafkaTopics() kafkaTopics {
	return kafkaTopics{
		request:          envOrDefault("KAFKA_REQUEST_TOPIC", "systems.agregator"),
		response:         envOrDefault("KAFKA_RESPONSE_TOPIC", "components.agregator.responses"),
		dlt:              envOrDefault("KAFKA_DLT_TOPIC", "errors.dead_letters"),
		operator:         envOrDefault("KAFKA_OPERATOR_TOPIC", "components.agregator.operator.requests"),
		operatorResponse: envOrDefault("KAFKA_OPERATOR_RESPONSE_TOPIC", "components.agregator.operator.responses"),
	}
}

func envOrDefault(key, fallback string) string {
	if v := strings.TrimSpace(os.Getenv(key)); v != "" {
		return v
	}
	return fallback
}

func waitForKafkaReady(t *testing.T, brokers []string) {
	t.Helper()

	deadline := time.Now().Add(90 * time.Second)
	for time.Now().Before(deadline) {
		for _, broker := range brokers {
			conn, err := net.DialTimeout("tcp", broker, defaultDialTimeout)
			if err == nil {
				_ = conn.Close()
				return
			}
		}
		time.Sleep(time.Second)
	}

	t.Fatalf("kafka is unreachable, checked brokers: %v", brokers)
}

type orderView struct {
	ID           string  `json:"id"`
	Status       string  `json:"status"`
	OperatorID   string  `json:"operator_id"`
	OfferedPrice float64 `json:"offered_price"`
}

func waitForOrderStatus(t *testing.T, baseURL, orderID, expectedStatus, token string) orderView {
	t.Helper()

	deadline := time.Now().Add(defaultKafkaReadTimeout)
	for time.Now().Before(deadline) {
		resp := doRequestWithAuth(t, "GET", baseURL+"/orders/"+orderID, nil, token)
		if resp.StatusCode != 200 {
			_ = resp.Body.Close()
			t.Fatalf("unexpected status for GET /orders/{id}: %d", resp.StatusCode)
		}

		var order orderView
		decodeJSON(t, resp.Body, &order)
		_ = resp.Body.Close()

		if order.Status == expectedStatus {
			return order
		}

		time.Sleep(500 * time.Millisecond)
	}

	t.Fatalf("order %s did not reach status %q in time", orderID, expectedStatus)
	return orderView{}
}

func createOrderForKafkaFlow(t *testing.T, baseURL string) (string, authSession) {
	t.Helper()

	customer := registerCustomerSession(t, baseURL)
	orderID, _ := createOrderWithCustomer(t, baseURL, customer)
	return orderID, customer
}

func mustUnmarshalJSON(t *testing.T, data []byte, out any) {
	t.Helper()
	if err := json.Unmarshal(data, out); err != nil {
		t.Fatalf("failed to unmarshal json: %v", err)
	}
}

func uniqueID(prefix string) string {
	return fmt.Sprintf("%s-%d", prefix, time.Now().UnixNano())
}
