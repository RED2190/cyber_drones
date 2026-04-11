# DummyComponent

Шаблон компонента дрона.

## Операции

| Operation | Описание | Parameters |
|-----------|----------|------------|
| echo | Возвращает данные | любые |
| increment | Увеличивает счётчик | value: int |
| get_state | Возвращает состояние | - |

## Использование

```python
from components.dummy_component.src import DummyComponent

component = DummyComponent(event_bus)
```
