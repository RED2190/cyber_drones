package analytics_component

import (
	"encoding/json"

	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/response"
)

const Topic = "components.agregator.analytics"

var Actions = []models.MessageType{
	models.MsgGetAnalytics,
}

func Handles(action models.MessageType) bool {
	for _, candidate := range Actions {
		if candidate == action {
			return true
		}
	}
	return false
}

type Handler struct{}

func NewHandler() *Handler {
	return &Handler{}
}

func (h *Handler) Handle(req models.Request) (models.Response, bool) {
	if !Handles(req.Action) {
		return models.Response{}, false
	}

	var payload models.GetAnalyticsRequest
	if err := json.Unmarshal(req.Payload, &payload); err != nil {
		return response.Err("analytics_component", req, "invalid payload: "+err.Error()), true
	}
	_ = payload

	return response.Ok(req, models.GetAnalyticsResponse{
		TotalOrders:     42,
		CompletedOrders: 38,
		ActiveContracts: 4,
		TotalRevenue:    125000,
		Disputes:        2,
	}), true
}
