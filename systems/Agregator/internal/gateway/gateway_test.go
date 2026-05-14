package gateway

import (
	"testing"
	"time"

	"github.com/kirilltahmazidi/aggregator/internal/handler"
	"github.com/kirilltahmazidi/aggregator/internal/models"
)

func TestComponentForKnownAction(t *testing.T) {
	gw := New(handler.New())

	component, ok := gw.ComponentFor(models.MsgCreateOrder)
	if !ok {
		t.Fatal("expected create_order to be routable")
	}
	if component != ComponentOrders {
		t.Fatalf("ComponentFor(create_order) = %q, want %q", component, ComponentOrders)
	}
}

func TestRouteUnknownAction(t *testing.T) {
	gw := New(handler.New())
	req := models.Request{
		Action:        models.MessageType("unknown_action"),
		CorrelationID: "corr-1",
		Timestamp:     time.Now().UTC().Format(time.RFC3339Nano),
	}

	resp := gw.Route(req)
	if resp.Success {
		t.Fatal("expected unknown action to fail")
	}
	if resp.Action != models.ResponseAction {
		t.Fatalf("response action = %q, want %q", resp.Action, models.ResponseAction)
	}
	if resp.CorrelationID != "corr-1" {
		t.Fatalf("correlation_id = %q, want corr-1", resp.CorrelationID)
	}
}
