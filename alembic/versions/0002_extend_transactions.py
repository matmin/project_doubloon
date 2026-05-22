from alembic import op

revision = "0002_extend_transactions"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE transactions ADD COLUMN transaction_type VARCHAR(20) DEFAULT 'expense'")
    op.execute("ALTER TABLE transactions ADD COLUMN is_work_expense BOOLEAN DEFAULT 0")
    op.execute("ALTER TABLE transactions ADD COLUMN reimbursement_status VARCHAR(20) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN reimbursement_amount DECIMAL(10,2) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN reimbursement_date DATE DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN reimbursement_notes TEXT DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN source_bank VARCHAR(50) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN external_id VARCHAR(200) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN isin VARCHAR(12) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN asset_type VARCHAR(50) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN shares DECIMAL(20,8) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN price_per_share DECIMAL(20,8) DEFAULT NULL")
    op.execute("ALTER TABLE transactions ADD COLUMN fee DECIMAL(10,2) DEFAULT 0")
    op.execute("ALTER TABLE transactions ADD COLUMN tax DECIMAL(10,2) DEFAULT 0")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_tx_source_extid "
        "ON transactions(user_id, source_bank, external_id) "
        "WHERE external_id IS NOT NULL"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_tx_type ON transactions(transaction_type)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_tx_isin ON transactions(isin)")


def downgrade():
    # SQLite < 3.35 cannot DROP COLUMN safely; leave as no-op for personal DB
    pass
