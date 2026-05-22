from alembic import op

revision = "0006_financial_goals"
down_revision = "0005_reimbursement_links"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS financial_goals (
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
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS financial_goals")
