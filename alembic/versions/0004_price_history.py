from alembic import op

revision = "0004_price_history"
down_revision = "0003_portfolio_positions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS price_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            isin VARCHAR(12),
            ticker VARCHAR(20),
            price_date DATE NOT NULL,
            price DECIMAL(20,8) NOT NULL,
            currency VARCHAR(3) DEFAULT 'EUR',
            source VARCHAR(50) DEFAULT 'yfinance',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(isin, ticker, price_date)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_ph_isin_date ON price_history(isin, price_date DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS isin_ticker_cache (
            isin VARCHAR(12) PRIMARY KEY,
            ticker VARCHAR(20) NOT NULL,
            yahoo_symbol VARCHAR(30),
            asset_name TEXT,
            source VARCHAR(20) DEFAULT 'manual',
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS price_history")
    op.execute("DROP TABLE IF EXISTS isin_ticker_cache")
