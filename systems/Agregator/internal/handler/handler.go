package handler

import (
	"fmt"

	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/internal/response"
	"github.com/kirilltahmazidi/aggregator/src/analytics_component"
	"github.com/kirilltahmazidi/aggregator/src/contracts_component"
	"github.com/kirilltahmazidi/aggregator/src/orders_component"
	"github.com/kirilltahmazidi/aggregator/src/registry_component"
)

type componentHandler interface {
	Handle(req models.Request) (models.Response, bool)
}

type Handler struct {
	components []componentHandler
}

func New() *Handler {
	return &Handler{
		components: []componentHandler{
			registry_component.NewHandler(),
			orders_component.NewHandler(),
			contracts_component.NewHandler(),
			analytics_component.NewHandler(),
		},
	}
}

// Handle — основная точка диспетчеризации: передаёт сообщение в реальный компонент из src/.
func (h *Handler) Handle(req models.Request) models.Response {
	for _, component := range h.components {
		if resp, ok := component.Handle(req); ok {
			return resp
		}
	}
	return response.Err("handler", req, fmt.Sprintf("unknown action: %s", req.Action))
}
