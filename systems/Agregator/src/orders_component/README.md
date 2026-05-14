## Компонент заказов

Компонент обрабатывает операции:

- `create_order`
- `select_executor`
- `auto_search_executor`
- сценариев работы с `price_offer` и `confirm_price`

Код обработки входящих bus-сообщений находится в `component.go`.
HTTP-часть и инфраструктурные зависимости пока остаются в `internal/`.
