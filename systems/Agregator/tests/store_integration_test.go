package tests

import (
	"database/sql"
	"math"
	"net/http"
	"os"
	"testing"
	"time"

	_ "github.com/jackc/pgx/v5/stdlib"
)

func TestStoreConfirmPricePersistsAmounts(t *testing.T) {
	dbURL := os.Getenv("TEST_DB_URL")
	if dbURL == "" {
		t.Skip("skipping store integration test: TEST_DB_URL is not set")
	}

	db, err := sql.Open("pgx", dbURL)
	if err != nil {
		t.Fatalf("failed to open db: %v", err)
	}
	defer db.Close()

	if err := db.Ping(); err != nil {
		t.Fatalf("failed to ping db: %v", err)
	}

	fx := newKafkaFixture(t)
	baseURL := mustResolveBaseURL(t)
	orderID, customer := createOrderForKafkaFlow(t, baseURL)

	operatorID := uniqueID("operator-db-check")
	offeredPrice := 2780.75
	fx.sendEnvelope(t, fx.operatorResponseTopic, orderID, "price_offer", map[string]any{
		"order_id":               orderID,
		"operator_id":            operatorID,
		"operator_name":          "DB Check Operator",
		"price":                  offeredPrice,
		"estimated_time_minutes": 15,
	})

	_ = waitForOrderStatus(t, baseURL, orderID, "matched", customer.Token)

	acceptedPrice := 2100.0
	confirmResp := doJSONRequestWithAuth(t, http.MethodPost, baseURL+"/orders/"+orderID+"/confirm-price", map[string]any{
		"operator_id":    operatorID,
		"accepted_price": acceptedPrice,
	}, customer.Token)
	defer confirmResp.Body.Close()
	if confirmResp.StatusCode != http.StatusOK {
		t.Fatalf("unexpected status for confirm-price request: %d", confirmResp.StatusCode)
	}

	var confirmBody struct {
		OrderID          string  `json:"order_id"`
		Status           string  `json:"status"`
		AcceptedPrice    float64 `json:"accepted_price"`
		CommissionAmount float64 `json:"commission_amount"`
		OperatorAmount   float64 `json:"operator_amount"`
	}
	decodeJSON(t, confirmResp.Body, &confirmBody)

	time.Sleep(150 * time.Millisecond)

	var (
		dbStatus           string
		dbOfferedPrice     float64
		dbCommissionAmount float64
		dbOperatorAmount   float64
	)
	err = db.QueryRow(
		`SELECT status, offered_price, commission_amount, operator_amount FROM orders WHERE id = $1`,
		orderID,
	).Scan(&dbStatus, &dbOfferedPrice, &dbCommissionAmount, &dbOperatorAmount)
	if err != nil {
		t.Fatalf("failed to query order row: %v", err)
	}

	if dbStatus != "confirmed" || confirmBody.Status != "confirmed" {
		t.Fatalf("expected confirmed status in API and DB, got api=%q db=%q", confirmBody.Status, dbStatus)
	}
	if math.Abs(dbOfferedPrice-confirmBody.AcceptedPrice) > 0.0001 {
		t.Fatalf("offered_price mismatch: api=%v db=%v", confirmBody.AcceptedPrice, dbOfferedPrice)
	}
	if math.Abs(dbCommissionAmount-confirmBody.CommissionAmount) > 0.0001 {
		t.Fatalf("commission_amount mismatch: api=%v db=%v", confirmBody.CommissionAmount, dbCommissionAmount)
	}
	if math.Abs(dbOperatorAmount-confirmBody.OperatorAmount) > 0.0001 {
		t.Fatalf("operator_amount mismatch: api=%v db=%v", confirmBody.OperatorAmount, dbOperatorAmount)
	}
}
