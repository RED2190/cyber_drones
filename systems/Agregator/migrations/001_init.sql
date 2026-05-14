-- Заказчики (пользователи, которые создают заказы)
CREATE TABLE IF NOT EXISTS customers (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    email       TEXT NOT NULL,
    phone       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Эксплуатанты (компании которые выполняют доставку дронами)
CREATE TABLE IF NOT EXISTS operators (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    mission_type  TEXT NOT NULL DEFAULT 'delivery',  -- delivery | agro
    security_goals TEXT[] NOT NULL DEFAULT '{}',     -- цели безопасности заказа
    top_left_lat   DOUBLE PRECISION NOT NULL DEFAULT 0,
    top_left_lon   DOUBLE PRECISION NOT NULL DEFAULT 0,
    bottom_right_lat DOUBLE PRECISION NOT NULL DEFAULT 0,
    bottom_right_lon DOUBLE PRECISION NOT NULL DEFAULT 0,
    commission_amount NUMERIC(12, 2) NOT NULL DEFAULT 0, -- сервисный сбор агрегатора
    operator_amount   NUMERIC(12, 2) NOT NULL DEFAULT 0, -- сумма к перечислению оператору (после комиссии)
    license     TEXT NOT NULL,
    email       TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Заказы на доставку
CREATE TABLE IF NOT EXISTS orders (
    id            TEXT PRIMARY KEY,
    customer_id   TEXT NOT NULL REFERENCES customers(id),
    description   TEXT NOT NULL,
    budget        NUMERIC(12, 2) NOT NULL DEFAULT 0,
    from_lat      DOUBLE PRECISION NOT NULL DEFAULT 0,
    from_lon      DOUBLE PRECISION NOT NULL DEFAULT 0,
    to_lat        DOUBLE PRECISION NOT NULL DEFAULT 0,
    to_lon        DOUBLE PRECISION NOT NULL DEFAULT 0,
    status        TEXT NOT NULL DEFAULT 'pending',
    operator_id   TEXT NOT NULL DEFAULT '',          -- заполняется когда эксплуатант даёт оферту
    offered_price NUMERIC(12, 2) NOT NULL DEFAULT 0, -- цена предложенная эксплуатантом
    mission_type  TEXT NOT NULL DEFAULT 'delivery',
    security_goals TEXT[] NOT NULL DEFAULT '{}',
    top_left_lat   DOUBLE PRECISION NOT NULL DEFAULT 0,
    top_left_lon   DOUBLE PRECISION NOT NULL DEFAULT 0,
    bottom_right_lat DOUBLE PRECISION NOT NULL DEFAULT 0,
    bottom_right_lon DOUBLE PRECISION NOT NULL DEFAULT 0,
    commission_amount NUMERIC(12, 2) NOT NULL DEFAULT 0, -- сервисный сбор агрегатора
    operator_amount   NUMERIC(12, 2) NOT NULL DEFAULT 0, -- сумма к перечислению оператору
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- На случай уже существующей таблицы без новых колонок — добиваем их идемпотентно
ALTER TABLE orders
    ADD COLUMN IF NOT EXISTS operator_id TEXT NOT NULL DEFAULT '',
    ADD COLUMN IF NOT EXISTS offered_price NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS mission_type TEXT NOT NULL DEFAULT 'delivery',
    ADD COLUMN IF NOT EXISTS security_goals TEXT[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS top_left_lat DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS top_left_lon DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bottom_right_lat DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS bottom_right_lon DOUBLE PRECISION NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS commission_amount NUMERIC(12, 2) NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS operator_amount NUMERIC(12, 2) NOT NULL DEFAULT 0;

-- Индекс для быстрого поиска заказов по заказчику
CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders(customer_id);
-- Индекс для фильтрации по статусу
CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
