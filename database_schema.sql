-- Database schema completo per Doubloon — Personal Finance Platform

-- Tabella utenti
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabella categorie spese
CREATE TABLE categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL UNIQUE,
    parent_category_id INTEGER,
    category_type VARCHAR(20) CHECK(category_type IN ('necessity', 'extra', 'investment', 'transfer', 'work')),
    is_shared BOOLEAN DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (parent_category_id) REFERENCES categories(id)
);

-- Tabella conti bancari
CREATE TABLE bank_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    bank_name VARCHAR(100) NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    account_number VARCHAR(50),
    account_type VARCHAR(20) CHECK(account_type IN ('current', 'savings', 'credit')),
    api_credentials_encrypted TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Tabella transazioni
CREATE TABLE transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_id INTEGER,
    transaction_date DATE NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    description TEXT NOT NULL,
    payee VARCHAR(200),
    category_id INTEGER,
    is_shared BOOLEAN DEFAULT 0,
    shared_split_percentage DECIMAL(5,2) DEFAULT 50.00,
    is_classified BOOLEAN DEFAULT 0,
    classification_confidence DECIMAL(5,2),
    notes TEXT,
    import_source VARCHAR(50),
    original_data TEXT,
    -- Fase 1 extensions
    transaction_type VARCHAR(20) DEFAULT 'expense',  -- expense|investment|transfer|income
    is_work_expense BOOLEAN DEFAULT 0,
    reimbursement_status VARCHAR(20) DEFAULT NULL,   -- NULL|pending|submitted|reimbursed
    reimbursement_amount DECIMAL(10,2) DEFAULT NULL,
    reimbursement_date DATE DEFAULT NULL,
    reimbursement_notes TEXT DEFAULT NULL,
    source_bank VARCHAR(50) DEFAULT NULL,
    external_id VARCHAR(200) DEFAULT NULL,
    isin VARCHAR(12) DEFAULT NULL,
    asset_type VARCHAR(50) DEFAULT NULL,
    shares DECIMAL(20,8) DEFAULT NULL,
    price_per_share DECIMAL(20,8) DEFAULT NULL,
    fee DECIMAL(10,2) DEFAULT 0,
    tax DECIMAL(10,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (account_id) REFERENCES bank_accounts(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

-- Tabella partner_balances
CREATE TABLE partner_balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL,
    to_user_id INTEGER NOT NULL,
    amount DECIMAL(10,2) NOT NULL,
    description TEXT,
    is_settled BOOLEAN DEFAULT 0,
    transaction_id INTEGER,
    settled_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (from_user_id) REFERENCES users(id),
    FOREIGN KEY (to_user_id) REFERENCES users(id),
    FOREIGN KEY (transaction_id) REFERENCES transactions(id)
);

-- Investimenti: posizioni materializzate
CREATE TABLE portfolio_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    isin VARCHAR(12),
    ticker VARCHAR(20),
    asset_name TEXT NOT NULL,
    asset_type VARCHAR(50),
    broker VARCHAR(50) NOT NULL,
    shares DECIMAL(20,8) NOT NULL DEFAULT 0,
    avg_cost_per_share DECIMAL(20,8),
    total_cost_basis DECIMAL(10,2),
    current_price DECIMAL(20,8),
    current_price_date DATE,
    currency VARCHAR(3) DEFAULT 'EUR',
    is_active BOOLEAN DEFAULT 1,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, isin, broker)
);

-- Cache prezzi di mercato
CREATE TABLE price_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    isin VARCHAR(12),
    ticker VARCHAR(20),
    price_date DATE NOT NULL,
    price DECIMAL(20,8) NOT NULL,
    currency VARCHAR(3) DEFAULT 'EUR',
    source VARCHAR(50) DEFAULT 'yfinance',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(isin, ticker, price_date)
);

-- Cache ISIN → ticker
CREATE TABLE isin_ticker_cache (
    isin VARCHAR(12) PRIMARY KEY,
    ticker VARCHAR(20) NOT NULL,
    yahoo_symbol VARCHAR(30),
    asset_name TEXT,
    source VARCHAR(20) DEFAULT 'manual',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Collegamento rimborso aggregato ↔ spese
CREATE TABLE reimbursement_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reimbursement_transaction_id INTEGER NOT NULL,
    expense_transaction_id INTEGER NOT NULL,
    allocated_amount DECIMAL(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reimbursement_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    FOREIGN KEY (expense_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
    UNIQUE(reimbursement_transaction_id, expense_transaction_id)
);

-- Obiettivi finanziari
CREATE TABLE financial_goals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(200) NOT NULL,
    goal_type VARCHAR(30),
    target_amount DECIMAL(12,2) NOT NULL,
    target_date DATE,
    current_amount DECIMAL(12,2) DEFAULT 0,
    monthly_contribution DECIMAL(10,2) DEFAULT 0,
    status VARCHAR(20) DEFAULT 'active',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Storico simulazioni
CREATE TABLE simulation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    scenario_name VARCHAR(200),
    simulation_type VARCHAR(30),
    inputs_json TEXT NOT NULL,
    results_json TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Snapshot patrimonio netto
CREATE TABLE networth_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    snapshot_date DATE NOT NULL,
    cash_amount DECIMAL(12,2) DEFAULT 0,
    investments_amount DECIMAL(12,2) DEFAULT 0,
    real_estate_amount DECIMAL(12,2) DEFAULT 0,
    other_assets_amount DECIMAL(12,2) DEFAULT 0,
    mortgage_debt DECIMAL(12,2) DEFAULT 0,
    other_debts DECIMAL(12,2) DEFAULT 0,
    net_worth DECIMAL(12,2) NOT NULL,
    source VARCHAR(20) DEFAULT 'manual',
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(user_id, snapshot_date)
);

-- Budget per categoria per mese
CREATE TABLE budget_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    category_id INTEGER NOT NULL,
    period_year INTEGER NOT NULL,
    period_month INTEGER,
    target_amount DECIMAL(10,2) NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (category_id) REFERENCES categories(id),
    UNIQUE(user_id, category_id, period_year, period_month)
);

-- Indici per ottimizzazione
CREATE INDEX idx_transactions_date ON transactions(transaction_date);
CREATE INDEX idx_transactions_user_date ON transactions(user_id, transaction_date);
CREATE INDEX idx_transactions_category ON transactions(category_id);
CREATE INDEX idx_tx_type ON transactions(transaction_type);
CREATE INDEX idx_tx_isin ON transactions(isin);
CREATE UNIQUE INDEX idx_tx_source_extid ON transactions(user_id, source_bank, external_id)
    WHERE external_id IS NOT NULL;
CREATE INDEX idx_pp_user ON portfolio_positions(user_id, is_active);
CREATE INDEX idx_ph_isin_date ON price_history(isin, price_date DESC);
CREATE INDEX idx_rl_reimb ON reimbursement_links(reimbursement_transaction_id);
CREATE INDEX idx_rl_expense ON reimbursement_links(expense_transaction_id);
