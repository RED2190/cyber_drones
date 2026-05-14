package registry_component

import (
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/response"
)

const Topic = "components.agregator.registry"

var Actions = []models.MessageType{
	models.MsgRegisterOperator,
	models.MsgRegisterCustomer,
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
	switch req.Action {
	case models.MsgRegisterOperator:
		return h.registerOperator(req), true
	case models.MsgRegisterCustomer:
		return h.registerCustomer(req), true
	default:
		return models.Response{}, false
	}
}

func (h *Handler) registerOperator(req models.Request) models.Response {
	var payload models.RegisterOperatorRequest
	if err := json.Unmarshal(req.Payload, &payload); err != nil {
		return response.Err("registry_component", req, "invalid payload: "+err.Error())
	}

	return response.Ok(req, models.RegisterOperatorResponse{
		OperatorID: uuid.NewString(),
		Message:    fmt.Sprintf("operator '%s' registered (stub)", payload.Name),
	})
}

func (h *Handler) registerCustomer(req models.Request) models.Response {
	var payload models.RegisterCustomerRequest
	if err := json.Unmarshal(req.Payload, &payload); err != nil {
		return response.Err("registry_component", req, "invalid payload: "+err.Error())
	}

	return response.Ok(req, models.RegisterCustomerResponse{
		CustomerID: uuid.NewString(),
		Message:    fmt.Sprintf("customer '%s' registered (stub)", payload.Name),
	})
}
