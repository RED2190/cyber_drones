package store_test

import (
	"os"
	"testing"

	"github.com/google/uuid"
	"github.com/kirilltahmazidi/aggregator/internal/store"
)

func TestOrderStateTransitions(t *testing.T) {
	dbURL := os.Getenv("TEST_DB_URL")
	if dbURL == "" {
		t.Skip("Skipping integration test, TEST_DB_URL is not set")
	}

	st, err := store.New(dbURL)
	if err != nil {
		t.Fatalf("failed to connect to db: %v", err)
	}
	defer st.Close()

	// 1. Создаем пользователя и заказ (для внешнего ключа)
	customerID := uuid.NewString()
	orderID := uuid.NewString()
	operatorID := uuid.NewString()
	
	// Вставляем заказ через методы хранилища
	err = st.SaveOrder(&store.Order{
		ID:          orderID,
		CustomerID:  customerID,
		Status:      store.StatusPending,
		Description: "test desc",
		MissionType: "delivery",
	})
	if err != nil {
		t.Fatalf("insert order error: %v", err)
	}

	// После публикации заказа API переводит его в searching.
	if ok := st.UpdateOrderStatus(orderID, store.StatusSearching); !ok {
		t.Fatalf("expected UpdateOrderStatus to move order into searching")
	}

	// --- ТЕСТ: price_offer (SetOperatorOffer) ---
	ok := st.SetOperatorOffer(orderID, operatorID, 500)
	if !ok {
		t.Errorf("Expected SetOperatorOffer to succeed for searching status")
	}

	// Повторная отправка должна быть проигнорирована (идемпотентность Both режимов)
	ok = st.SetOperatorOffer(orderID, operatorID, 500)
	if ok {
		t.Errorf("Expected second SetOperatorOffer to fail (order is matched, not searching)")
	}

	// --- ТЕСТ: confirm_price (ConfirmPrice) ---
	ok = st.ConfirmPrice(orderID, operatorID, 500, 50)
	if !ok {
		t.Errorf("Expected ConfirmPrice to succeed from matched status")
	}

	// Попытка подтвердить выполнение раньше времени -> false
	ok = st.ConfirmCompletion(orderID)
	if ok {
		t.Errorf("Expected ConfirmCompletion to fail (order is confirmed, not completed_pending_confirmation)")
	}

	// --- ТЕСТ: order_result (ProcessOrderResult) ---
	ok = st.ProcessOrderResult(orderID, true)
	if !ok {
		t.Errorf("Expected ProcessOrderResult to succeed for confirmed status")
	}

	// Повторная отправка order_result -> false
	ok = st.ProcessOrderResult(orderID, true)
	if ok {
		t.Errorf("Expected second ProcessOrderResult to fail")
	}

	// --- ТЕСТ: confirm_completion (ConfirmCompletion) ---
	ok = st.ConfirmCompletion(orderID)
	if !ok {
		t.Errorf("Expected ConfirmCompletion to succeed from completed_pending_confirmation")
	}
}
