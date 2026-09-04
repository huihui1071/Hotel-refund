PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    display_name TEXT NOT NULL,
    mobile_masked TEXT NOT NULL,
    identity_status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS hotels (
    hotel_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    city TEXT NOT NULL,
    country TEXT NOT NULL,
    star_level INTEGER,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS suppliers (
    supplier_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    type TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policies (
    policy_id TEXT PRIMARY KEY,
    version TEXT NOT NULL,
    scenario TEXT NOT NULL,
    requires_human INTEGER NOT NULL CHECK (requires_human IN (0, 1)),
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    hotel_id TEXT NOT NULL REFERENCES hotels(hotel_id),
    supplier_id TEXT NOT NULL REFERENCES suppliers(supplier_id),
    policy_id TEXT NOT NULL REFERENCES policies(policy_id),
    payment_id TEXT NOT NULL,
    refund_id TEXT,
    status TEXT NOT NULL,
    version INTEGER NOT NULL,
    check_in TEXT NOT NULL,
    check_out TEXT NOT NULL,
    timezone TEXT NOT NULL,
    paid_amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_orders_user ON orders(user_id);
CREATE INDEX IF NOT EXISTS idx_orders_scenario ON orders(scenario_id);

CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payment_events (
    event_id TEXT PRIMARY KEY,
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    event_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_id TEXT NOT NULL REFERENCES payments(payment_id),
    status TEXT NOT NULL,
    amount INTEGER NOT NULL,
    currency TEXT NOT NULL,
    waiting_for TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    conversation_state TEXT NOT NULL,
    case_status TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    waiting_for TEXT NOT NULL,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS case_events (
    event_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    event_type TEXT NOT NULL,
    actor_type TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    from_case_status TEXT,
    to_case_status TEXT,
    public_summary TEXT NOT NULL,
    idempotency_key TEXT,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_case_events_case ON case_events(case_id, occurred_at);

CREATE TABLE IF NOT EXISTS external_cases (
    external_case_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    waiting_for TEXT NOT NULL,
    response_due_at TEXT,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_items (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    type TEXT NOT NULL,
    storage TEXT NOT NULL,
    user_confirmed INTEGER NOT NULL CHECK (user_confirmed IN (0, 1)),
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS alternative_hotels (
    source_order_id TEXT NOT NULL REFERENCES orders(order_id),
    hotel_id TEXT NOT NULL REFERENCES hotels(hotel_id),
    available INTEGER NOT NULL CHECK (available IN (0, 1)),
    price_difference INTEGER NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (source_order_id, hotel_id)
);

CREATE TABLE IF NOT EXISTS scenario_fixtures (
    scenario_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    expected_route TEXT NOT NULL,
    expected_case_status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fixture_catalog (
    fixture_type TEXT NOT NULL,
    fixture_key TEXT NOT NULL,
    phase TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    PRIMARY KEY (fixture_type, fixture_key, phase)
);

CREATE TABLE IF NOT EXISTS tool_contracts (
    tool_name TEXT PRIMARY KEY,
    mode TEXT NOT NULL CHECK (mode IN ('READ', 'WRITE')),
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id),
    case_id TEXT REFERENCES cases(case_id),
    confirmed_order_id TEXT REFERENCES orders(order_id),
    conversation_state TEXT NOT NULL,
    state_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS confirmation_tokens (
    token TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    tool_name TEXT NOT NULL,
    order_id TEXT,
    expected_version INTEGER,
    action_fingerprint TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed_at TEXT
);

CREATE TABLE IF NOT EXISTS idempotency_records (
    idempotency_key TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    request_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS scheduled_actions (
    action_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    deadline TEXT NOT NULL,
    action_type TEXT NOT NULL,
    status TEXT NOT NULL,
    payload_json TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS workflow_runs (
    run_id TEXT PRIMARY KEY,
    scenario_id TEXT NOT NULL,
    session_id TEXT NOT NULL REFERENCES sessions(session_id),
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    route TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    result_json TEXT
);

CREATE TABLE IF NOT EXISTS workflow_steps (
    step_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES workflow_runs(run_id),
    sequence_no INTEGER NOT NULL,
    workflow_node TEXT NOT NULL,
    actor TEXT NOT NULL,
    tool_name TEXT,
    state_before TEXT,
    state_after TEXT,
    result_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    UNIQUE (run_id, sequence_no)
);

CREATE TABLE IF NOT EXISTS tool_executions (
    execution_id TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    mode TEXT NOT NULL,
    trace_id TEXT NOT NULL,
    session_id TEXT,
    case_id TEXT,
    order_id TEXT,
    request_json TEXT NOT NULL,
    response_json TEXT NOT NULL,
    occurred_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tool_exec_trace ON tool_executions(trace_id);
