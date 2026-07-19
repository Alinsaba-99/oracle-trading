-- Oracle G3 — Ledger & OMS Schema (PostgreSQL)
--
-- This schema defines the durable, authoritative state for accounts,
-- orders, fills, positions, and the transactional outbox.
--
-- In development/test, SQLite is used with minor dialect adjustments
-- (e.g. BIGSERIAL → INTEGER, JSONB → TEXT, pgcrypto → uuid).
--
-- Source of truth target: PostgreSQL
-- Dev/test: SQLite (same schema, adapted types)

-- =========================================================================
-- Accounts
-- =========================================================================

CREATE TABLE IF NOT EXISTS accounts (
    account_id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Unique account identifier (matches prop-firm account id where applicable)

    account_type        TEXT NOT NULL CHECK (account_type IN (
                            'paper', 'shadow', 'evaluation', 'funded'
                        )),
    mode                TEXT NOT NULL DEFAULT 'research',
    -- OracleMode at account creation

    status              TEXT NOT NULL DEFAULT 'active'
                        CHECK (status IN ('active', 'suspended', 'closed')),

    -- Initial / current balance
    initial_balance     NUMERIC(20, 8) NOT NULL,
    currency            TEXT NOT NULL DEFAULT 'USD',

    -- Ledger invariants (derived, NOT NULL with CHECK)
    current_balance     NUMERIC(20, 8) NOT NULL,
    -- current_balance = initial_balance + SUM(all realized P&L) - SUM(fees)

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Optimistic concurrency
    version             INTEGER NOT NULL DEFAULT 1,

    CONSTRAINT positive_initial CHECK (initial_balance > 0),
    CONSTRAINT balance_invariant CHECK (current_balance >= 0)
);

CREATE INDEX idx_accounts_mode ON accounts(mode);
CREATE INDEX idx_accounts_status ON accounts(status);

-- =========================================================================
-- Orders
-- =========================================================================

CREATE TABLE IF NOT EXISTS orders (
    order_id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Internal Oracle order ID

    account_id          UUID NOT NULL REFERENCES accounts(account_id),

    -- Client-supplied idempotency key (unique per account)
    client_order_id     TEXT NOT NULL,
    -- Used for idempotent retry: same client_order_id + account = no-op

    broker_order_id     TEXT,
    -- Broker-assigned order ID (populated after submit)

    instrument_id       TEXT NOT NULL,
    side                TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
    order_type          TEXT NOT NULL CHECK (order_type IN (
                            'market', 'limit', 'stop', 'stop_limit'
                        )),
    quantity            NUMERIC(20, 8) NOT NULL CHECK (quantity > 0),
    price               NUMERIC(20, 8),
    stop_price          NUMERIC(20, 8),
    time_in_force       TEXT NOT NULL DEFAULT 'day'
                        CHECK (time_in_force IN ('day', 'gtc', 'ioc', 'fok')),
    execution_algo      TEXT,

    -- Status lifecycle: pending → submitted → (filled | cancelled | rejected)
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN (
                            'pending', 'submitted', 'partially_filled',
                            'filled', 'cancelled', 'rejected', 'expired'
                        )),

    filled_quantity     NUMERIC(20, 8) NOT NULL DEFAULT 0,
    avg_fill_price      NUMERIC(20, 8),

    -- Source
    source              TEXT NOT NULL DEFAULT 'api'
                        CHECK (source IN ('api', 'cli', 'mas', 'system', 'manual')),
    strategy_id         TEXT,

    -- Error / reject info
    reject_reason       TEXT,
    error_message       TEXT,

    -- Timestamps
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    submitted_at        TIMESTAMPTZ,
    filled_at           TIMESTAMPTZ,
    cancelled_at        TIMESTAMPTZ,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    version             INTEGER NOT NULL DEFAULT 1,

    -- Enforce idempotency: unique client_order_id per account
    UNIQUE (account_id, client_order_id)
);

CREATE INDEX idx_orders_account ON orders(account_id);
CREATE INDEX idx_orders_status ON orders(status);
CREATE INDEX idx_orders_broker ON orders(broker_order_id);
CREATE INDEX idx_orders_instrument ON orders(instrument_id);

-- =========================================================================
-- Fills
-- =========================================================================

CREATE TABLE IF NOT EXISTS fills (
    fill_id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Unique fill identifier (Oracle-generated)

    order_id            UUID NOT NULL REFERENCES orders(order_id),
    account_id          UUID NOT NULL REFERENCES accounts(account_id),

    broker_fill_id      TEXT,
    -- Broker-assigned fill ID (used for duplicate detection)

    quantity            NUMERIC(20, 8) NOT NULL CHECK (quantity > 0),
    price               NUMERIC(20, 8) NOT NULL CHECK (price > 0),
    commission          NUMERIC(20, 8) NOT NULL DEFAULT 0,
    realized_pnl        NUMERIC(20, 8) NOT NULL DEFAULT 0,

    fill_time           TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Duplicate prevention
    idempotency_key     TEXT,
    UNIQUE (order_id, broker_fill_id)
);

CREATE INDEX idx_fills_order ON fills(order_id);
CREATE INDEX idx_fills_account ON fills(account_id);
CREATE INDEX idx_fills_broker ON fills(broker_fill_id);

-- =========================================================================
-- Positions
-- =========================================================================

CREATE TABLE IF NOT EXISTS positions (
    position_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    account_id          UUID NOT NULL REFERENCES accounts(account_id),
    instrument_id       TEXT NOT NULL,

    side                TEXT NOT NULL CHECK (side IN ('long', 'short')),
    quantity            NUMERIC(20, 8) NOT NULL CHECK (quantity >= 0),
    avg_entry_price     NUMERIC(20, 8),
    current_price       NUMERIC(20, 8),

    realized_pnl        NUMERIC(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl      NUMERIC(20, 8) NOT NULL DEFAULT 0,

    -- Snapshot timestamp
    as_of               TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (account_id, instrument_id)
);

CREATE INDEX idx_positions_account ON positions(account_id);
CREATE INDEX idx_positions_instrument ON positions(instrument_id);

-- =========================================================================
-- Transactional Outbox (for event-driven integration)
-- =========================================================================

CREATE TABLE IF NOT EXISTS outbox (
    outbox_id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Aggregate root reference
    aggregate_type      TEXT NOT NULL,
    aggregate_id        TEXT NOT NULL,

    -- Event metadata
    event_type          TEXT NOT NULL,
    event_version       INTEGER NOT NULL DEFAULT 1,
    payload             JSONB NOT NULL,

    -- Delivery tracking
    status              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'published', 'failed')),
    published_at        TIMESTAMPTZ,
    retry_count         INTEGER NOT NULL DEFAULT 0,
    max_retries         INTEGER NOT NULL DEFAULT 3,
    last_error          TEXT,

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_outbox_status ON outbox(status, created_at)
    WHERE status = 'pending';
CREATE INDEX idx_outbox_aggregate ON outbox(aggregate_type, aggregate_id);

-- =========================================================================
-- Account Snapshots (for reconciliation audit)
-- =========================================================================

CREATE TABLE IF NOT EXISTS account_snapshots (
    snapshot_id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    account_id          UUID NOT NULL REFERENCES accounts(account_id),

    balance             NUMERIC(20, 8) NOT NULL,
    equity              NUMERIC(20, 8) NOT NULL,
    margin_used         NUMERIC(20, 8) NOT NULL DEFAULT 0,
    unrealized_pnl      NUMERIC(20, 8) NOT NULL DEFAULT 0,

    -- Full position snapshot (JSON for flexibility)
    positions           JSONB NOT NULL DEFAULT '[]',

    snapshot_time       TIMESTAMPTZ NOT NULL DEFAULT now(),
    reason              TEXT NOT NULL DEFAULT 'scheduled'
                        CHECK (reason IN ('scheduled', 'startup', 'on_demand', 'reconciliation'))
);

CREATE INDEX idx_snapshots_account ON account_snapshots(account_id, snapshot_time DESC);

-- =========================================================================
-- Migration tracking
-- =========================================================================

CREATE TABLE IF NOT EXISTS schema_migrations (
    version             INTEGER PRIMARY KEY,
    applied_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    filename            TEXT NOT NULL,
    checksum            TEXT NOT NULL
);
