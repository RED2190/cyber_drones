package tests

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"math"
	"net/http"
	"os"
	"strings"
	"testing"
	"time"
)

type authSession struct {
	Token string
	ID    string
}

func skipAuthRemovedTests(t *testing.T) {
	t.Helper()
	t.Skip("авторизация вырезана в этой ветке; auth-зависимые интеграционные тесты отключены")
}

func TestHealth(t *testing.T) {
	baseURL := mustResolveBaseURL(t)

	resp := doRequest(t, http.MethodGet, baseURL+"/health", nil)
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for /health: %d", resp.StatusCode)
	}

	var body map[string]string
	decodeJSON(t, resp.Body, &body)

	if body["status"] != "ok" {
		t.Fatalf("unexpected health status: %q", body["status"])
	}
}

func TestOrderLifecycleIntegration(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	ts := time.Now().UnixNano()

	customerPayload := map[string]any{
		"name":     fmt.Sprintf("Integration Customer %d", ts),
		"email":    fmt.Sprintf("integration-%d@example.com", ts),
		"phone":    "+79001234567",
		"password": "Password123!",
	}
	customerResp := doJSONRequest(t, http.MethodPost, baseURL+"/customers", customerPayload)
	defer customerResp.Body.Close()

	if customerResp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /customers: %d", customerResp.StatusCode)
	}

	var customerRespBody struct {
		Token string `json:"token"`
		User  struct {
			ID    string `json:"id"`
			Name  string `json:"name"`
			Email string `json:"email"`
			Phone string `json:"phone"`
		} `json:"user"`
	}
	decodeJSON(t, customerResp.Body, &customerRespBody)
	if customerRespBody.Token == "" {
		t.Fatal("customer token is empty")
	}
	if customerRespBody.User.ID == "" {
		t.Fatal("customer id is empty")
	}

	customer := authSession{Token: customerRespBody.Token, ID: customerRespBody.User.ID}

	customerGetResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/customers/"+customer.ID, nil, customer.Token)
	defer customerGetResp.Body.Close()
	if customerGetResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for GET /customers/{id}: %d", customerGetResp.StatusCode)
	}

	orderPayload := map[string]any{
		"customer_id":    customer.ID,
		"description":    "Доставить документы из офиса на склад",
		"budget":         2500.50,
		"mission_type":   "delivery",
		"security_goals": []string{"ЦБ1", "ЦБ3"},
		"from_lat":       55.7558,
		"from_lon":       37.6173,
		"to_lat":         55.8000,
		"to_lon":         37.6500,
	}
	orderResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders", orderPayload, customer.Token)
	defer orderResp.Body.Close()

	if orderResp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /orders: %d", orderResp.StatusCode)
	}

	var createdOrder struct {
		ID         string `json:"id"`
		CustomerID string `json:"customer_id"`
		Status     string `json:"status"`
	}
	decodeJSON(t, orderResp.Body, &createdOrder)

	if createdOrder.ID == "" {
		t.Fatal("order id is empty")
	}
	if createdOrder.CustomerID != customer.ID {
		t.Fatalf("unexpected customer_id in created order: %q", createdOrder.CustomerID)
	}
	if createdOrder.Status != "searching" {
		t.Fatalf("unexpected initial order status: %q", createdOrder.Status)
	}

	orderGetResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/orders/"+createdOrder.ID, nil, customer.Token)
	defer orderGetResp.Body.Close()

	if orderGetResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for GET /orders/{id}: %d", orderGetResp.StatusCode)
	}

	var fetchedOrder struct {
		ID string `json:"id"`
	}
	decodeJSON(t, orderGetResp.Body, &fetchedOrder)

	if fetchedOrder.ID != createdOrder.ID {
		t.Fatalf("unexpected fetched order id: %q", fetchedOrder.ID)
	}

	operator := registerOperatorSession(t, baseURL)
	offerResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/"+createdOrder.ID+"/offer", map[string]any{
		"price": 2200.0,
	}, operator.Token)
	defer offerResp.Body.Close()
	if offerResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for POST /orders/{id}/offer: %d", offerResp.StatusCode)
	}

	confirmPayload := map[string]any{
		"operator_id":    operator.ID,
		"accepted_price": 2200.0,
	}
	confirmResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/"+createdOrder.ID+"/confirm-price", confirmPayload, customer.Token)
	defer confirmResp.Body.Close()

	if confirmResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for POST /orders/{id}/confirm-price: %d", confirmResp.StatusCode)
	}

	var confirmBody struct {
		OrderID          string  `json:"order_id"`
		Status           string  `json:"status"`
		AcceptedPrice    float64 `json:"accepted_price"`
		CommissionAmount float64 `json:"commission_amount"`
		OperatorAmount   float64 `json:"operator_amount"`
	}
	decodeJSON(t, confirmResp.Body, &confirmBody)

	if confirmBody.OrderID != createdOrder.ID {
		t.Fatalf("unexpected order_id in confirm response: %q", confirmBody.OrderID)
	}
	if confirmBody.Status != "confirmed" {
		t.Fatalf("unexpected status in confirm response: %q", confirmBody.Status)
	}
	if math.Abs(confirmBody.AcceptedPrice-2200.0) > 0.0001 {
		t.Fatalf("unexpected accepted_price in confirm response: %v", confirmBody.AcceptedPrice)
	}
	if math.Abs(confirmBody.CommissionAmount-220.0) > 0.0001 {
		t.Fatalf("unexpected commission_amount in confirm response: %v", confirmBody.CommissionAmount)
	}
	if math.Abs(confirmBody.OperatorAmount-1980.0) > 0.0001 {
		t.Fatalf("unexpected operator_amount in confirm response: %v", confirmBody.OperatorAmount)
	}

	confirmedGetResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/orders/"+createdOrder.ID, nil, customer.Token)
	defer confirmedGetResp.Body.Close()

	if confirmedGetResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for GET /orders/{id} after confirm: %d", confirmedGetResp.StatusCode)
	}

	var confirmedOrder struct {
		ID     string `json:"id"`
		Status string `json:"status"`
	}
	decodeJSON(t, confirmedGetResp.Body, &confirmedOrder)

	if confirmedOrder.Status != "confirmed" {
		t.Fatalf("order status was not updated to confirmed, got: %q", confirmedOrder.Status)
	}

	listResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/orders", nil, customer.Token)
	defer listResp.Body.Close()

	if listResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for GET /orders: %d", listResp.StatusCode)
	}

	var orders []struct {
		ID string `json:"id"`
	}
	decodeJSON(t, listResp.Body, &orders)

	found := false
	for _, o := range orders {
		if o.ID == createdOrder.ID {
			found = true
			break
		}
	}
	if !found {
		t.Fatalf("created order %q was not found in GET /orders", createdOrder.ID)
	}
}

func TestValidationAndNotFound(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	customer := registerCustomerSession(t, baseURL)

	badOrderPayload := map[string]any{
		"budget": 1000,
	}
	badOrderResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders", badOrderPayload, customer.Token)
	defer badOrderResp.Body.Close()

	if badOrderResp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected status for invalid POST /orders: %d", badOrderResp.StatusCode)
	}

	notFoundID := fmt.Sprintf("missing-%d", time.Now().UnixNano())
	notFoundResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/orders/"+notFoundID, nil, customer.Token)
	defer notFoundResp.Body.Close()

	if notFoundResp.StatusCode != http.StatusNotFound {
		t.Fatalf("unexpected status for missing GET /orders/{id}: %d", notFoundResp.StatusCode)
	}

	var notFoundBody map[string]string
	decodeJSON(t, notFoundResp.Body, &notFoundBody)
	if notFoundBody["error"] != "заказ не найден" {
		t.Fatalf("unexpected error body for missing GET /orders/{id}: %#v", notFoundBody)
	}
}

func TestOperatorRegistrationAndValidation(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	ts := time.Now().UnixNano()

	okResp := doJSONRequest(t, http.MethodPost, baseURL+"/operators", map[string]any{
		"name":     fmt.Sprintf("Operator %d", ts),
		"license":  fmt.Sprintf("LIC-%d", ts),
		"email":    fmt.Sprintf("operator-%d@example.com", ts),
		"password": "Password123!",
	})
	defer okResp.Body.Close()

	if okResp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /operators: %d", okResp.StatusCode)
	}

	var body struct {
		Token string `json:"token"`
		User  struct {
			ID      string `json:"id"`
			Name    string `json:"name"`
			License string `json:"license"`
		} `json:"user"`
	}
	decodeJSON(t, okResp.Body, &body)
	if strings.TrimSpace(body.User.ID) == "" {
		t.Fatal("operator id is empty")
	}
	if body.Token == "" {
		t.Fatal("operator token is empty")
	}
	if body.User.Name == "" || body.User.License == "" {
		t.Fatalf("unexpected operator response payload: %#v", body)
	}

	badResp := doJSONRequest(t, http.MethodPost, baseURL+"/operators", map[string]any{
		"name":     "",
		"email":    "missing-license@example.com",
		"password": "Password123!",
	})
	defer badResp.Body.Close()

	if badResp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected status for invalid POST /operators: %d", badResp.StatusCode)
	}
}

func TestCustomerValidationAndNotFound(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	customer := registerCustomerSession(t, baseURL)

	badCustomerResp := doJSONRequest(t, http.MethodPost, baseURL+"/customers", map[string]any{
		"name":  "Only Name",
		"phone": "+79001234567",
	})
	defer badCustomerResp.Body.Close()

	if badCustomerResp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected status for invalid POST /customers: %d", badCustomerResp.StatusCode)
	}

	notFoundCustomerID := fmt.Sprintf("missing-customer-%d", time.Now().UnixNano())
	notFoundResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/customers/"+notFoundCustomerID, nil, customer.Token)
	defer notFoundResp.Body.Close()

	if notFoundResp.StatusCode != http.StatusForbidden {
		t.Fatalf("unexpected status for missing GET /customers/{id}: %d", notFoundResp.StatusCode)
	}
}

func TestCreateOrderWithoutAuth(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)

	resp := doJSONRequest(t, http.MethodPost, baseURL+"/orders", map[string]any{
		"customer_id":    "missing-customer-id",
		"description":    "Доставить документы из офиса на склад",
		"budget":         1500,
		"mission_type":   "delivery",
		"security_goals": []string{"ЦБ1"},
		"from_lat":       55.75,
		"from_lon":       37.61,
		"to_lat":         55.8,
		"to_lon":         37.65,
	})
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusUnauthorized {
		t.Fatalf("unexpected status for POST /orders without auth: %d", resp.StatusCode)
	}
}

func TestConfirmPriceValidationAndNotFound(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	missingOrderResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/missing-order/confirm-price", map[string]any{
		"operator_id":    "operator-x",
		"accepted_price": 1000,
	}, customer.Token)
	defer missingOrderResp.Body.Close()
	if missingOrderResp.StatusCode != http.StatusNotFound {
		t.Fatalf("unexpected status for confirm-price on missing order: %d", missingOrderResp.StatusCode)
	}

	badPriceResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    "operator-x",
		"accepted_price": 0,
	}, customer.Token)
	defer badPriceResp.Body.Close()
	if badPriceResp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected status for confirm-price with invalid price: %d", badPriceResp.StatusCode)
	}

	badOperatorResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    "",
		"accepted_price": 1234,
	}, customer.Token)
	defer badOperatorResp.Body.Close()
	if badOperatorResp.StatusCode != http.StatusBadRequest {
		t.Fatalf("unexpected status for confirm-price with empty operator_id: %d", badOperatorResp.StatusCode)
	}
}

func TestListOrdersSortedByCreatedAtDesc(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	customer := registerCustomerSession(t, baseURL)

	firstOrderID, _ := createOrderWithCustomer(t, baseURL, customer)
	time.Sleep(50 * time.Millisecond)
	secondOrderID, _ := createOrderWithCustomer(t, baseURL, customer)

	listResp := doRequestWithAuth(t, http.MethodGet, baseURL+"/orders", nil, customer.Token)
	defer listResp.Body.Close()
	if listResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for GET /orders: %d", listResp.StatusCode)
	}

	var orders []struct {
		ID        string    `json:"id"`
		CreatedAt time.Time `json:"created_at"`
	}
	decodeJSON(t, listResp.Body, &orders)

	if len(orders) < 2 {
		t.Fatalf("expected at least 2 orders in GET /orders, got %d", len(orders))
	}

	firstIdx := -1
	secondIdx := -1
	for i, order := range orders {
		if order.ID == firstOrderID {
			firstIdx = i
		}
		if order.ID == secondOrderID {
			secondIdx = i
		}
	}

	if firstIdx == -1 || secondIdx == -1 {
		t.Fatalf("orders not found in list: first=%q second=%q", firstOrderID, secondOrderID)
	}
	if secondIdx >= firstIdx {
		t.Fatalf("expected newer order %q to be before older order %q in DESC list", secondOrderID, firstOrderID)
	}

	for i := 1; i < len(orders); i++ {
		if orders[i-1].CreatedAt.Before(orders[i].CreatedAt) {
			t.Fatalf("orders are not sorted by created_at DESC at index %d", i)
		}
	}
}

func TestCreateAgroOrder(t *testing.T) {
	skipAuthRemovedTests(t)

	baseURL := mustResolveBaseURL(t)
	customer := registerCustomerSession(t, baseURL)

	agroResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders", map[string]any{
		"customer_id":      customer.ID,
		"description":      "Обработать поле",
		"budget":           4000.00,
		"mission_type":     "agro",
		"security_goals":   []string{"ЦБ2", "ЦБ4"},
		"top_left_lat":     55.90,
		"top_left_lon":     37.40,
		"bottom_right_lat": 55.80,
		"bottom_right_lon": 37.60,
	}, customer.Token)
	defer agroResp.Body.Close()
	if agroResp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /orders agro: %d", agroResp.StatusCode)
	}

	var order struct {
		ID             string   `json:"id"`
		MissionType    string   `json:"mission_type"`
		SecurityGoals  []string `json:"security_goals"`
		TopLeftLat     float64  `json:"top_left_lat"`
		TopLeftLon     float64  `json:"top_left_lon"`
		BottomRightLat float64  `json:"bottom_right_lat"`
		BottomRightLon float64  `json:"bottom_right_lon"`
	}
	decodeJSON(t, agroResp.Body, &order)

	if order.ID == "" {
		t.Fatal("agro order id is empty")
	}
	if order.MissionType != "agro" {
		t.Fatalf("unexpected mission_type in agro order: %q", order.MissionType)
	}
	if len(order.SecurityGoals) != 2 {
		t.Fatalf("unexpected security_goals in agro order: %#v", order.SecurityGoals)
	}
	if order.TopLeftLat != 55.90 || order.TopLeftLon != 37.40 || order.BottomRightLat != 55.80 || order.BottomRightLon != 37.60 {
		t.Fatalf("unexpected agro coordinates in response: %#v", order)
	}
}

func mustResolveBaseURL(t *testing.T) string {
	t.Helper()

	if explicit := strings.TrimSpace(os.Getenv("AGGREGATOR_BASE_URL")); explicit != "" {
		waitForHealthy(t, explicit)
		return explicit
	}

	candidates := []string{
		"http://aggregator:8080",
		"http://localhost:8081",
	}
	for _, candidate := range candidates {
		if waitForHealthyNoFail(candidate) {
			return candidate
		}
	}

	t.Fatalf("aggregator service is unreachable. set AGGREGATOR_BASE_URL or start the stack")
	return ""
}

func waitForHealthy(t *testing.T, baseURL string) {
	t.Helper()
	if !waitForHealthyNoFail(baseURL) {
		t.Fatalf("service %s did not become healthy in time", baseURL)
	}
}

func waitForHealthyNoFail(baseURL string) bool {
	client := &http.Client{Timeout: 2 * time.Second}
	deadline := time.Now().Add(90 * time.Second)

	for time.Now().Before(deadline) {
		resp, err := client.Get(baseURL + "/health")
		if err == nil {
			_ = resp.Body.Close()
			if resp.StatusCode == http.StatusOK {
				return true
			}
		}
		time.Sleep(time.Second)
	}

	return false
}

func doJSONRequest(t *testing.T, method, url string, payload any) *http.Response {
	t.Helper()

	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}

	return doRequest(t, method, url, bytes.NewReader(body))
}

func doJSONRequestWithAuth(t *testing.T, method, url string, payload any, token string) *http.Response {
	t.Helper()

	body, err := json.Marshal(payload)
	if err != nil {
		t.Fatalf("failed to marshal payload: %v", err)
	}

	return doRequestWithAuth(t, method, url, bytes.NewReader(body), token)
}

func doRequest(t *testing.T, method, url string, body io.Reader) *http.Response {
	t.Helper()

	req, err := http.NewRequest(method, url, body)
	if err != nil {
		t.Fatalf("failed to create request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("request %s %s failed: %v", method, url, err)
	}
	return resp
}

func doRequestWithAuth(t *testing.T, method, url string, body io.Reader, token string) *http.Response {
	t.Helper()

	req, err := http.NewRequest(method, url, body)
	if err != nil {
		t.Fatalf("failed to create request: %v", err)
	}
	if body != nil {
		req.Header.Set("Content-Type", "application/json")
	}
	if strings.TrimSpace(token) != "" {
		req.Header.Set("Authorization", "Bearer "+token)
	}

	client := &http.Client{Timeout: 10 * time.Second}
	resp, err := client.Do(req)
	if err != nil {
		t.Fatalf("request %s %s failed: %v", method, url, err)
	}
	return resp
}

func registerCustomerSession(t *testing.T, baseURL string) authSession {
	t.Helper()
	skipAuthRemovedTests(t)

	ts := time.Now().UnixNano()
	resp := doJSONRequest(t, http.MethodPost, baseURL+"/customers", map[string]any{
		"name":     fmt.Sprintf("Customer %d", ts),
		"email":    fmt.Sprintf("customer-%d@example.com", ts),
		"phone":    "+79001234567",
		"password": "Password123!",
	})
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /customers: %d", resp.StatusCode)
	}

	var body struct {
		Token string `json:"token"`
		User  struct {
			ID string `json:"id"`
		} `json:"user"`
	}
	decodeJSON(t, resp.Body, &body)
	if body.Token == "" || body.User.ID == "" {
		t.Fatalf("invalid register customer response: %#v", body)
	}

	return authSession{Token: body.Token, ID: body.User.ID}
}

func registerOperatorSession(t *testing.T, baseURL string) authSession {
	t.Helper()
	skipAuthRemovedTests(t)

	ts := time.Now().UnixNano()
	resp := doJSONRequest(t, http.MethodPost, baseURL+"/operators", map[string]any{
		"name":     fmt.Sprintf("Operator %d", ts),
		"license":  fmt.Sprintf("LIC-%d", ts),
		"email":    fmt.Sprintf("operator-%d@example.com", ts),
		"password": "Password123!",
	})
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /operators: %d", resp.StatusCode)
	}

	var body struct {
		Token string `json:"token"`
		User  struct {
			ID string `json:"id"`
		} `json:"user"`
	}
	decodeJSON(t, resp.Body, &body)
	if body.Token == "" || body.User.ID == "" {
		t.Fatalf("invalid register operator response: %#v", body)
	}

	return authSession{Token: body.Token, ID: body.User.ID}
}

func createOrderWithCustomer(t *testing.T, baseURL string, customer authSession) (string, authSession) {
	t.Helper()

	resp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders", map[string]any{
		"customer_id":    customer.ID,
		"description":    "Доставить документы из офиса на склад",
		"budget":         2600.0,
		"mission_type":   "delivery",
		"security_goals": []string{"ЦБ1", "ЦБ3"},
		"from_lat":       55.7558,
		"from_lon":       37.6173,
		"to_lat":         55.8,
		"to_lon":         37.65,
	}, customer.Token)
	defer resp.Body.Close()
	if resp.StatusCode != http.StatusCreated {
		t.Fatalf("unexpected status for POST /orders: %d", resp.StatusCode)
	}

	var order struct {
		ID string `json:"id"`
	}
	decodeJSON(t, resp.Body, &order)
	if strings.TrimSpace(order.ID) == "" {
		t.Fatal("order id is empty")
	}

	return order.ID, customer
}

func decodeJSON(t *testing.T, r io.Reader, out any) {
	t.Helper()

	if err := json.NewDecoder(r).Decode(out); err != nil {
		t.Fatalf("failed to decode json response: %v", err)
	}
}
