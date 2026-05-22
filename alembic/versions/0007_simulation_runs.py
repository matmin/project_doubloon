from alembic import op

revision = "0007_simulation_runs"
down_revision = "0006_financial_goals"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS simulation_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            scenario_name VARCHAR(200),
            simulation_type VARCHAR(30),
            inputs_json TEXT NOT NULL,
            results_json TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS simulation_runs")
