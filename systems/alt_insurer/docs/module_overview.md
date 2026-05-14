# Alt Insurer: модуль и страховая математика

Документ описывает модуль `systems/alt_insurer/src/insurance_service`: какие формулы используются для расчета премий и какие основные API-действия поддерживаются через шину сообщений.

## Назначение

`alt_insurer` реализует альтернативную страховую логику для дронов:
- расчет премий;
- оформление годовых и миссионных полисов;
- фиксация инцидентов и пересчет коэффициентов риска;
- прекращение полиса по `order_id`.

Сервис хранит состояние в памяти процесса (in-memory):
- полисы (`_policies`);
- инциденты (`_incidents`);
- статистика по дрону (`_drone_stats`).

## Страховая математика

## 1) Годовой полис

Формула:

`Pannual = Vdrone * Rbase_hull * Kfleet_history`

Где:
- `Vdrone` - стоимость дрона (`drone_value`);
- `Rbase_hull` - базовая ставка корпуса (`base_hull_rate`) с ограничением диапазона `[0.05, 0.15]`;
- `Kfleet_history` - коэффициент истории эксплуатации:
  - `0.8`, если `flights_per_year > 100` и `accident_rate < 0.02`;
  - `1.5`, если `accident_rate > 0.05`;
  - `1.0` в остальных случаях (включая `flights_per_year < 10`).

## 2) Миссионный полис

Формула:

`Pmission = (Vcargo * Rrisk_class) * Kenv * Kincident_history`

Где:
- `Vcargo` - покрытие/стоимость миссии (`coverage_amount`);
- `Rrisk_class` - ставка класса риска по типу дрона:
  - `inspector = 0.01`
  - `delivery = 0.08` (значение по умолчанию)
  - `firefighter = 0.12`
- `Kenv` - коэффициент среды (`kenv`) с ограничением `[1.0, 2.0]`;
- `Kincident_history`:
  - базово `Kbase = 1.0`;
  - `Kbase = 0.8`, если `total_missions >= 500` и `incidents == 0`;
  - при `total_missions > 0`:
    `Kincident_history = Kbase + (incidents / total_missions) * leverage`,
    где `leverage` по умолчанию `2.0`.

## Основные API (через SystemBus)

## Топики

- системный топик gateway: `systems.alt_insurer`
- компонентный топик сервиса: `components.insurer_service`

Gateway принимает запросы на `systems.alt_insurer` и проксирует в `components.insurer_service`.

## Поддерживаемые actions

- `annual_insurance`
- `mission_insurance`
- `calculate_policy`
- `purchase_policy` (обрабатывается как `annual_insurance`)
- `report_incident`
- `terminate_policy`

## Базовая структура сообщения

Запрос:
- `action` - одно из действий выше;
- `sender` - идентификатор отправителя;
- `payload` - бизнес-поля.

Ответ:
- `success` - общий флаг обработки;
- `payload` - данные результата (`policy_id`, `premium`, коэффициенты, даты, сообщения).

## Минимальные payload поля по действиям

### `calculate_policy`
- `order_id`
- `drone_id`
- `coverage_amount`
- опционально: `drone_value`, `base_hull_rate`, `drone_type`, `kenv`, `leverage`

### `annual_insurance` / `purchase_policy`
- `order_id`
- `drone_id`
- `coverage_amount`
- опционально: `drone_value`, `base_hull_rate`, `manufacturer_id`, `operator_id`

### `mission_insurance`
- `order_id`
- `drone_id`
- `coverage_amount`
- опционально: `drone_type`, `kenv`, `leverage`

### `report_incident`
- `order_id`
- `drone_id`
- `incident` (или поля инцидента на верхнем уровне), включая `damage_amount`

### `terminate_policy`
- `order_id`

## Важные детали поведения

- При `mission_insurance` сервис увеличивает `total_missions` для дрона.
- При `report_incident` увеличивается `incidents`, а `accident_rate` пересчитывается как `incidents / total_missions` (если миссии уже есть).
- Сроки полисов:
  - annual: `365` дней;
  - mission: `24` часа.
- Все значения премий округляются до 2 знаков.
