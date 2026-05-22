from alembic import op

revision = "0008_networth_snapshots"
down_revision = "0007_simulation_runs"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS networth_snapshots (
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
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS networth_snapshots")
