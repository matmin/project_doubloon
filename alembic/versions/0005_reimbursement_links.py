from alembic import op

revision = "0005_reimbursement_links"
down_revision = "0004_price_history"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reimbursement_links (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reimbursement_transaction_id INTEGER NOT NULL,
            expense_transaction_id INTEGER NOT NULL,
            allocated_amount DECIMAL(10,2),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (reimbursement_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
            FOREIGN KEY (expense_transaction_id) REFERENCES transactions(id) ON DELETE CASCADE,
            UNIQUE(reimbursement_transaction_id, expense_transaction_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rl_reimb ON reimbursement_links(reimbursement_transaction_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_rl_expense ON reimbursement_links(expense_transaction_id)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS reimbursement_links")
