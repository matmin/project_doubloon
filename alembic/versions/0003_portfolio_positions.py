from alembic import op

revision = "0003_portfolio_positions"
down_revision = "0002_extend_transactions"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS portfolio_positions (
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
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_pp_user ON portfolio_positions(user_id, is_active)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS portfolio_positions")
