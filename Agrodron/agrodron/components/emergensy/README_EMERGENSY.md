## Компонент «emergensy» (Экстренные ситуации) агродрона

Этот документ описывает, **как другим компонентам системы взаимодействовать с компонентом экстренных ситуаций** через брокер сообщений.

Актуальная архитектура:

- у каждого компонента **1 входящий топик** `agrodron.<component>`;
- вход в компонент — **только от МБ** (`security_monitor`);
- компоненты **не подписываются** на чужие топики;
- любые данные (включая позицию) получаются только через `proxy_request` (polling) через МБ.

---

## 1. Назначение компонента

`emergensy` реализует **аварийный протокол посадки**, который запускается при событии от ограничителя о выходе за допустимые границы выполнения миссии.

Протокол:

1. Запустить через монитор безопасности (МБ) **протокол изоляции** (нужно отправить определённую команду в МБ; МБ выполняет изоляцию сам).
2. Отправить в опрыскиватель команду на **закрытие распыления**.
3. Отправить в приводы команду на **посадку**.
4. (Опционально) Получить актуальную позицию от навигации **через `proxy_request`** и приложить её к событию/журналу.

Компонент не занимается анализом отклонений — это делает `limiter`.

---

## 2. Используемые форматы данных (общие для системы)

### 2.1. Формат миссии (для справки)

Ограничитель и автопилот используют упрощённый формат миссии:

```json
{
  "mission_id": "mission-1",
  "home": { "lat": 60.0, "lon": 30.0, "alt_m": 0.0 },
  "steps": [
    { "id": "wp-001", "type": "WAYPOINT", "lat": 60.123456, "lon": 30.123456, "alt_m": 5.0, "speed_mps": 5.0, "spray": false }
  ]
}
```

### 2.2. Формат навигационных данных

Навигация должна уметь отдавать snapshot состояния по запросу (например `action=get_state` на топике `agrodron.navigation`):

```json
{
  "timestamp": "2026-03-09T12:00:01.234Z",
  "lat": 60.123450,
  "lon": 30.123400,
  "alt_m": 4.9,
  "ground_speed_mps": 4.8,
  "heading_deg": 90.0,
  "fix": "3D",
  "satellites": 14,
  "hdop": 0.7
}
```

---

## 3. Топик и actions компонента `emergensy`

### 3.1. Входящий топик

1. **Топик**: `agrodron.emergensy`
2. **Кто пишет**: только МБ при проксировании.
3. **Ключевой вход**: `action = "limiter_event"`

`emergensy` реагирует на `payload.event = "EMERGENCY_LAND_REQUIRED"`.

   Пример входного сообщения:

   ```json
   {
     "action": "limiter_event",
     "sender": "security_monitor_...",
     "payload": {
       "event": "EMERGENCY_LAND_REQUIRED",
       "mission_id": "mission-1",
       "details": { "distance_from_path_m": 15.0, "max_distance_from_path_m": 10.0 }
     }
   }
   ```

### 3.2. Исходящие действия `emergensy` (все через МБ)

1. **Команда в монитор безопасности (МБ) для изоляции**
   - Топик: `agrodron.security_monitor`
   - Назначение: запуск изоляции.

   Сообщение:

   ```json
   {
     "action": "ISOLATION_START",
     "sender": "emergensy",
     "payload": {
       "reason": "LIMITER_EMERGENCY",
       "mission_id": "mission-1"
     }
   }
   ```

   > Конкретная реализация изоляции — зона ответственности МБ; `emergensy` только инициирует её.

2. **Команда опрыскивателю на закрытие распыления**
   - Через `proxy_publish` в `agrodron.sprayer` / `SET_SPRAY`

   Сообщение в МБ:

   ```json
   {
     "action": "proxy_publish",
     "sender": "emergensy",
     "payload": {
       "target": { "topic": "agrodron.sprayer", "action": "SET_SPRAY" },
       "data": { "spray": false }
     }
   }
   ```

3. **Команда приводам на посадку**
   - Через `proxy_publish` в `agrodron.motors` / `LAND`

   Сообщение в МБ:

   ```json
   {
     "action": "proxy_publish",
     "sender": "emergensy",
     "payload": {
       "target": { "topic": "agrodron.motors", "action": "LAND" },
       "data": { "mode": "AUTO_LAND" }
     }
   }
   ```

4. **Журналирование**
   - Через `proxy_publish` в `agrodron.journal` / `LOG_EVENT`

   Пример в МБ:

   ```json
   {
     "action": "proxy_publish",
     "sender": "emergensy",
     "payload": {
       "target": { "topic": "agrodron.journal", "action": "LOG_EVENT" },
       "data": {
         "event": "EMERGENCY_PROTOCOL_STARTED",
         "mission_id": "mission-1",
         "details": { "...": "..." }
       }
     }
   }
   ```

---

## 4. Логика работы (кратко)

1. Получать `limiter_event` на своём топике `agrodron.emergensy` (доставляет МБ).
2. При получении `EMERGENCY_LAND_REQUIRED`:
   - (а) отправить `ISOLATION_START` в МБ;
   - (б) отправить `SET_SPRAY` с `spray=false` в опрыскиватель;
   - (в) отправить `LAND` в приводы;
   - (г) (опционально) запросить позицию у `navigation` через `proxy_request` и записать событие в `journal`.

Компонент рассчитан на прототип/SITL: достаточно гарантировать **порядок команд и их однозначность**.

---

## 5. Параметры `.env` (основные)

См. `components/emergensy/.env.example`.

