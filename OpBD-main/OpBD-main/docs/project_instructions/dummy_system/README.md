# DummySystem (пример системы)

Шаблон для создания новой системы.

Демонстрирует, что **система собирается из нескольких Docker-контейнеров**:
- `dummy_component_a` — компонент A (BaseComponent), слушает `components.dummy_component`
- `dummy_component_b` — компонент B (BaseComponent), слушает `components.dummy_component`

Контейнеры общаются через единую шину (Kafka/MQTT).

## Структура

```
src/
  dummy.py         Реализация системы
  topics.py        Топики и actions
tests/
  test_dummy_unit.py     Unit тесты
  test_integration.py    Интеграционные тесты (docker required)
docker/
  Dockerfile
  docker-compose.yml     Система + компонент + брокер
  example.env
__main__.py        Точка входа
Makefile           Сборка и тесты
```

## Запуск

```bash
make unit-test           # Unit тесты (без Docker)
make integration-test    # Интеграционные тесты (с Docker)
make docker-up           # Поднять систему (координатор + компонент + брокер)
make docker-down         # Остановить
```

## Как адаптировать

1. Скопируй эту папку в отдельный репо
2. Переименуй класс в `src/`
3. Обнови топики и actions в `src/topics.py`
4. Добавь свои handlers
5. Добавь нужные компоненты в `docker-compose.yml`
