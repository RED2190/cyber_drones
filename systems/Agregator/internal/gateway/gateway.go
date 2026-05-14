package gateway

import (
	"fmt"

	"github.com/kirilltahmazidi/aggregator/internal/handler"
	"github.com/kirilltahmazidi/aggregator/internal/models"
	"github.com/kirilltahmazidi/aggregator/src/analytics_component"
	"github.com/kirilltahmazidi/aggregator/src/contracts_component"
	"github.com/kirilltahmazidi/aggregator/src/orders_component"
	"github.com/kirilltahmazidi/aggregator/src/registry_component"
)

const (
	ComponentRegistry  = registry_component.Topic
	ComponentOrders    = orders_component.Topic
	ComponentContracts = contracts_component.Topic
	ComponentAnalytics = analytics_component.Topic
)

// ActionRouting описывает, какой внутренний компонент отвечает за action.
// В текущем сервисе обработка остаётся in-process, но таблица маршрутизации
// явно задаёт API gateway и упрощает дальнейшее вынесение компонентов.
var ActionRouting = map[models.MessageType]string{
	models.MsgRegisterOperator:   ComponentRegistry,
	models.MsgRegisterCustomer:   ComponentRegistry,
	models.MsgCreateOrder:        ComponentOrders,
	models.MsgSelectExecutor:     ComponentOrders,
	models.MsgAutoSearchExecutor: ComponentOrders,
	models.MsgConcludeContract:   ComponentContracts,
	models.MsgConfirmExecution:   ComponentContracts,
	models.MsgCreateDispute:      ComponentContracts,
	models.MsgGetAnalytics:       ComponentAnalytics,
}

type Gateway struct {
	handler *handler.Handler
}

func New(h *handler.Handler) *Gateway {
	return &Gateway{handler: h}
}

func (g *Gateway) Route(req models.Request) models.Response {
	if _, ok := ActionRouting[req.Action]; !ok {
		return models.Response{
			Action:        models.ResponseAction,
			Sender:        models.DefaultSender,
			CorrelationID: req.GetCorrelationID(),
			Success:       false,
			Error:         fmt.Sprintf("unknown action: %s", req.Action),
			Timestamp:     req.Timestamp,
		}
	}
	return g.handler.Handle(req)
}

func (g *Gateway) ComponentFor(action models.MessageType) (string, bool) {
	component, ok := ActionRouting[action]
	return component, ok
}
