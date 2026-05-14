## Компонент контрактов

Компонент обрабатывает операции:

- `conclude_contract`
- `confirm_execution`
- `create_dispute`

Код обработки входящих bus-сообщений находится в `component.go`.
Компонент вызывается через gateway, а общий слой совместимости остаётся в
`internal/handler`.
