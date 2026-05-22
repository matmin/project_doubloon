from alembic import op

revision = "0009_budget_targets"
down_revision = "0008_networth_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_targets (
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
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS budget_targets")
