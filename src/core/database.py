import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self, db_path="data/expense_tracker.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(exist_ok=True, parents=True)
        self._initialize_database()

    @contextmanager
    def get_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys=ON;")
            yield conn
        except Exception as e:
            if conn:
                conn.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            if conn:
                conn.close()

    def _initialize_database(self):
        schema_path = Path(__file__).parent.parent.parent / "database_schema.sql"
        if not schema_path.exists():
            raise FileNotFoundError(f"database_schema.sql not found at {schema_path}")

        # Check if database exists and has tables
        db_needs_creation = not self.db_path.exists()
        if not db_needs_creation:
            # Check if tables exist
            try:
                with self.get_connection() as conn:
                    cursor = conn.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
                    )
                    if not cursor.fetchone():
                        db_needs_creation = True
            except Exception:
                db_needs_creation = True

        if db_needs_creation:
            logger.info("Creating database...")
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            with self.get_connection() as conn:
                conn.executescript(schema_sql)
                conn.commit()
            logger.info("Database schema created")

    def create_user(self, name, email):
        with self.get_connection() as conn:
            cursor = conn.execute("INSERT INTO users (name,email) VALUES (?,?)", (name, email))
            conn.commit()
            return cursor.lastrowid

    def get_all_users(self):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users ORDER BY name")
            users = [dict(row) for row in cursor.fetchall()]
            return users

    def get_user_by_name(self, name: str):
        with self.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM users WHERE LOWER(name) = LOWER(?)", (name,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_or_create_user(self, name: str, email: str):
        user = self.get_user_by_name(name)
        if user:
            return user["id"]
        return self.create_user(name, email)

    def get_category_by_name(self, name: str):
        with self.get_connection() as conn:
            cur = conn.execute("SELECT * FROM categories WHERE name = ?", (name,))
            row = cur.fetchone()
            return dict(row) if row else None

    def create_transaction(
        self,
        user_id,
        transaction_date,
        amount,
        description,
        category_id=None,
        is_shared=False,
        shared_split=50.0,
    ):
        with self.get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO transactions
                (user_id,transaction_date,amount,description,category_id,is_shared,shared_split_percentage)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    user_id,
                    transaction_date,
                    amount,
                    description,
                    category_id,
                    is_shared,
                    shared_split,
                ),
            )
            conn.commit()
            transaction_id = cursor.lastrowid
            if is_shared and amount < 0:
                self._create_partner_balance(conn, user_id, transaction_id, amount, shared_split)
            return transaction_id

    def upsert_transaction_if_new(
        self,
        user_id,
        transaction_date,
        amount,
        description,
        category_id=None,
        is_shared=False,
        shared_split=50.0,
    ):
        """Insert transaction if not a likely duplicate.
        Duplicate heuristic: same user_id, date, amount, description.
        Returns (inserted: bool, transaction_id: int|None)
        """
        with self.get_connection() as conn:
            cur = conn.execute(
                """
                SELECT id FROM transactions
                WHERE user_id = ? AND transaction_date = ? AND amount = ? AND description = ?
                LIMIT 1
                """,
                (user_id, transaction_date, amount, description),
            )
            row = cur.fetchone()
            if row:
                return False, row[0]
            cursor = conn.execute(
                """INSERT INTO transactions
                (user_id,transaction_date,amount,description,category_id,is_shared,shared_split_percentage)
                VALUES (?,?,?,?,?,?,?)""",
                (
                    user_id,
                    transaction_date,
                    amount,
                    description,
                    category_id,
                    is_shared,
                    shared_split,
                ),
            )
            conn.commit()
            tx_id = cursor.lastrowid
            if is_shared and amount < 0:
                self._create_partner_balance(conn, user_id, tx_id, amount, shared_split)
            return True, tx_id

    def update_transaction_classification(
        self,
        transaction_id: int,
        *,
        category_id=None,
        is_shared=None,
        confidence: float | None = None,
        notes: str | None = None,
    ):
        """Update classification fields and optionally category and is_shared."""
        fields = []
        params = []
        if category_id is not None:
            fields.append("category_id = ?")
            params.append(category_id)
        if is_shared is not None:
            fields.append("is_shared = ?")
            params.append(1 if is_shared else 0)
        if confidence is not None:
            fields.append("classification_confidence = ?")
            params.append(confidence)
        # mark as classified if any classification info provided
        if confidence is not None or category_id is not None or is_shared is not None:
            fields.append("is_classified = 1")
        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)
        if not fields:
            return 0
        params.append(transaction_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            return 1

    def update_transaction_metadata(
        self,
        transaction_id: int,
        *,
        notes: str | None = None,
        import_source: str | None = None,
        original_data: str | None = None,
        payee: str | None = None,
    ):
        fields = []
        params = []
        if notes is not None:
            fields.append("notes = ?")
            params.append(notes)
        if import_source is not None:
            fields.append("import_source = ?")
            params.append(import_source)
        if original_data is not None:
            fields.append("original_data = ?")
            params.append(original_data)
        if payee is not None:
            fields.append("payee = ?")
            params.append(payee)
        if not fields:
            return 0
        params.append(transaction_id)
        with self.get_connection() as conn:
            conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id = ?", params)
            conn.commit()
            return 1

    def bulk_insert_transactions(self, transactions):
        """Insert many transactions with duplicate check. transactions is iterable of dicts
        keys: user_id, transaction_date, amount, description, optional category_id,is_shared,shared_split
        Returns number of inserted records.
        """
        inserted = 0
        for t in transactions:
            created, _ = self.upsert_transaction_if_new(
                t["user_id"],
                t["transaction_date"],
                t["amount"],
                t["description"],
                t.get("category_id"),
                t.get("is_shared", False),
                t.get("shared_split", 50.0),
            )
            if created:
                inserted += 1
        return inserted

    def _create_partner_balance(self, conn, payer_id, transaction_id, amount, split_percentage):
        cursor = conn.execute("SELECT id FROM users WHERE id != ? LIMIT 1", (payer_id,))
        partner = cursor.fetchone()
        if partner:
            partner_id = partner[0]
            partner_owes = abs(amount) * (split_percentage / 100)
            conn.execute(
                "INSERT INTO partner_balances (from_user_id,to_user_id,amount,transaction_id,description) VALUES (?,?,?,?,?)",
                (partner_id, payer_id, partner_owes, transaction_id, "Quota spesa condivisa"),
            )

    def get_transactions(self, user_id=None, start_date=None, end_date=None, limit=100):
        query = """SELECT t.*, c.name as category_name, u.name as user_name
                   FROM transactions t
                   LEFT JOIN categories c ON t.category_id = c.id
                   LEFT JOIN users u ON t.user_id = u.id
                   WHERE 1=1"""
        params = []
        if user_id:
            query += " AND t.user_id = ?"
            params.append(user_id)
        if start_date:
            query += " AND t.transaction_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND t.transaction_date <= ?"
            params.append(end_date)
        query += " ORDER BY t.transaction_date DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def get_partner_balances(self, user_id=None):
        with self.get_connection() as conn:
            if user_id:
                cursor = conn.execute(
                    """SELECT pb.*, u1.name as from_user_name, u2.name as to_user_name
                    FROM partner_balances pb
                    JOIN users u1 ON pb.from_user_id = u1.id
                    JOIN users u2 ON pb.to_user_id = u2.id
                    WHERE (pb.from_user_id = ? OR pb.to_user_id = ?) AND pb.is_settled = 0
                    ORDER BY pb.created_at DESC""",
                    (user_id, user_id),
                )
            else:
                cursor = conn.execute(
                    """SELECT pb.*, u1.name as from_user_name, u2.name as to_user_name
                    FROM partner_balances pb
                    JOIN users u1 ON pb.from_user_id = u1.id
                    JOIN users u2 ON pb.to_user_id = u2.id
                    WHERE pb.is_settled = 0
                    ORDER BY pb.created_at DESC"""
                )
            return [dict(row) for row in cursor.fetchall()]

    def setup_default_categories(self):
        """Load categories and subcategories from config/default_categories.json if not present."""
        import json

        config_path = Path(__file__).parent.parent.parent / "config" / "default_categories.json"
        if not config_path.exists():
            logger.warning("default_categories.json not found; skipping default categories setup")
            return 0
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        created = 0
        with self.get_connection() as conn:
            for cat in data.get("categories", []):
                name = cat.get("name")
                category_type = cat.get("type")
                is_shared = 1 if name in ("Necessità", "Extra") else 0
                # Upsert main category
                cursor = conn.execute("SELECT id FROM categories WHERE name = ?", (name,))
                row = cursor.fetchone()
                if row:
                    parent_id = row[0]
                else:
                    cur2 = conn.execute(
                        "INSERT INTO categories (name, category_type, is_shared) VALUES (?,?,?)",
                        (name, category_type, is_shared),
                    )
                    parent_id = cur2.lastrowid
                    created += 1
                # Insert subcategories
                for sub in cat.get("subcategories", []):
                    cursor = conn.execute("SELECT id FROM categories WHERE name = ?", (sub,))
                    if not cursor.fetchone():
                        conn.execute(
                            "INSERT INTO categories (name, parent_category_id, category_type, is_shared) VALUES (?,?,?,?)",
                            (sub, parent_id, category_type, is_shared),
                        )
                        created += 1
            conn.commit()
        logger.info(f"Default categories setup completed. Created: {created}")
        return created

    def reset_database(self):
        """Reset the entire database - DANGEROUS!"""
        # Drop the entire database file and recreate it
        if self.db_path.exists():
            self.db_path.unlink()
        logger.warning("Database file deleted!")

        # Recreate database using the same initialization logic
        self._initialize_database()
        logger.warning("Database has been completely reset and recreated!")

    # ------------------------------------------------------------------
    # Investment transactions
    # ------------------------------------------------------------------

    def upsert_investment_transaction(self, user_id: int, data: dict) -> tuple[bool, int]:
        """Insert investment transaction with dedup on (user_id, source_bank, external_id)."""
        external_id = data.get("external_id")
        source_bank = data.get("source_bank")
        if external_id and source_bank:
            with self.get_connection() as conn:
                cur = conn.execute(
                    "SELECT id FROM transactions WHERE user_id=? AND source_bank=? AND external_id=?",
                    (user_id, source_bank, external_id),
                )
                row = cur.fetchone()
                if row:
                    return False, row[0]
        # Fallback dedup: date + amount + description
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT id FROM transactions WHERE user_id=? AND transaction_date=? AND amount=? AND description=? LIMIT 1",
                (user_id, data["transaction_date"], data["amount"], data["description"]),
            )
            if cur.fetchone():
                return False, -1

        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO transactions (
                    user_id, transaction_date, amount, description, currency,
                    import_source, original_data, transaction_type, source_bank,
                    external_id, isin, asset_type, shares, price_per_share, fee, tax
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    user_id,
                    data["transaction_date"],
                    data["amount"],
                    data.get("description", ""),
                    data.get("currency", "EUR"),
                    data.get("source_bank"),
                    data.get("original_data"),
                    data.get("transaction_type", "investment"),
                    source_bank,
                    external_id,
                    data.get("isin"),
                    data.get("asset_type"),
                    data.get("shares"),
                    data.get("price_per_share"),
                    data.get("fee", 0),
                    data.get("tax", 0),
                ),
            )
            conn.commit()
            return True, cur.lastrowid

    def get_investment_transactions(
        self,
        user_id: int,
        broker: str | None = None,
        isin: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        query = """
            SELECT * FROM transactions
            WHERE user_id = ? AND transaction_type = 'investment'
        """
        params: list = [user_id]
        if broker:
            query += " AND source_bank = ?"
            params.append(broker)
        if isin:
            query += " AND isin = ?"
            params.append(isin)
        if start_date:
            query += " AND transaction_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND transaction_date <= ?"
            params.append(end_date)
        query += " ORDER BY transaction_date ASC"
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Portfolio positions
    # ------------------------------------------------------------------

    def upsert_portfolio_position(self, pos: dict) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT id FROM portfolio_positions WHERE user_id=? AND isin=? AND broker=?",
                (pos["user_id"], pos.get("isin"), pos.get("broker")),
            )
            row = cur.fetchone()
            if row:
                conn.execute(
                    """UPDATE portfolio_positions SET
                        ticker=?, asset_name=?, asset_type=?, shares=?,
                        avg_cost_per_share=?, total_cost_basis=?, is_active=?,
                        last_updated=CURRENT_TIMESTAMP
                    WHERE id=?""",
                    (
                        pos.get("ticker"),
                        pos.get("asset_name", ""),
                        pos.get("asset_type"),
                        pos.get("shares", 0),
                        pos.get("avg_cost_per_share"),
                        pos.get("total_cost_basis"),
                        1 if pos.get("is_active", True) else 0,
                        row[0],
                    ),
                )
                conn.commit()
                return row[0]
            cur = conn.execute(
                """INSERT INTO portfolio_positions (
                    user_id, isin, ticker, asset_name, asset_type, broker,
                    shares, avg_cost_per_share, total_cost_basis, is_active
                ) VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    pos["user_id"],
                    pos.get("isin"),
                    pos.get("ticker"),
                    pos.get("asset_name", ""),
                    pos.get("asset_type"),
                    pos.get("broker", "Unknown"),
                    pos.get("shares", 0),
                    pos.get("avg_cost_per_share"),
                    pos.get("total_cost_basis"),
                    1 if pos.get("is_active", True) else 0,
                ),
            )
            conn.commit()
            return cur.lastrowid

    def get_portfolio_positions(self, user_id: int) -> list[dict]:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM portfolio_positions WHERE user_id=? ORDER BY is_active DESC, total_cost_basis DESC",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def update_position_price(self, position_id: int, price: float) -> None:
        from datetime import date
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE portfolio_positions SET current_price=?, current_price_date=?, last_updated=CURRENT_TIMESTAMP WHERE id=?",
                (price, date.today().isoformat(), position_id),
            )
            conn.commit()

    # ------------------------------------------------------------------
    # Price history / ISIN cache
    # ------------------------------------------------------------------

    def save_price(self, isin: str, ticker: str, price_date: str, price: float) -> None:
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO price_history (isin, ticker, price_date, price)
                   VALUES (?,?,?,?)
                   ON CONFLICT(isin, ticker, price_date) DO UPDATE SET price=excluded.price""",
                (isin, ticker, price_date, price),
            )
            conn.commit()

    def get_latest_price(self, isin: str) -> dict | None:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT * FROM price_history WHERE isin=? ORDER BY price_date DESC LIMIT 1",
                (isin,),
            )
            row = cur.fetchone()
            return dict(row) if row else None

    def save_isin_ticker(self, isin: str, ticker: str, source: str = "manual") -> None:
        with self.get_connection() as conn:
            conn.execute(
                """INSERT INTO isin_ticker_cache (isin, ticker, source)
                   VALUES (?,?,?)
                   ON CONFLICT(isin) DO UPDATE SET ticker=excluded.ticker, source=excluded.source,
                   updated_at=CURRENT_TIMESTAMP""",
                (isin, ticker, source),
            )
            conn.commit()

    def get_isin_ticker(self, isin: str) -> str | None:
        with self.get_connection() as conn:
            cur = conn.execute(
                "SELECT ticker FROM isin_ticker_cache WHERE isin=?",
                (isin,),
            )
            row = cur.fetchone()
            return row[0] if row else None

    # ------------------------------------------------------------------
    # Networth snapshots
    # ------------------------------------------------------------------

    def upsert_networth_snapshot(self, user_id: int, data: dict) -> int:
        with self.get_connection() as conn:
            net = (
                float(data.get("cash_amount", 0))
                + float(data.get("investments_amount", 0))
                + float(data.get("real_estate_amount", 0))
                + float(data.get("other_assets_amount", 0))
                - float(data.get("mortgage_debt", 0))
                - float(data.get("other_debts", 0))
            )
            conn.execute(
                """INSERT INTO networth_snapshots (
                    user_id, snapshot_date, cash_amount, investments_amount,
                    real_estate_amount, other_assets_amount, mortgage_debt,
                    other_debts, net_worth, source, notes
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(user_id, snapshot_date) DO UPDATE SET
                    cash_amount=excluded.cash_amount,
                    investments_amount=excluded.investments_amount,
                    real_estate_amount=excluded.real_estate_amount,
                    other_assets_amount=excluded.other_assets_amount,
                    mortgage_debt=excluded.mortgage_debt,
                    other_debts=excluded.other_debts,
                    net_worth=excluded.net_worth,
                    source=excluded.source,
                    notes=excluded.notes""",
                (
                    user_id,
                    data["snapshot_date"],
                    data.get("cash_amount", 0),
                    data.get("investments_amount", 0),
                    data.get("real_estate_amount", 0),
                    data.get("other_assets_amount", 0),
                    data.get("mortgage_debt", 0),
                    data.get("other_debts", 0),
                    net,
                    data.get("source", "manual"),
                    data.get("notes"),
                ),
            )
            conn.commit()
            cur = conn.execute(
                "SELECT id FROM networth_snapshots WHERE user_id=? AND snapshot_date=?",
                (user_id, data["snapshot_date"]),
            )
            return cur.fetchone()[0]

    def get_networth_snapshots(
        self, user_id: int, start_date: str | None = None, limit: int = 200
    ) -> list[dict]:
        query = "SELECT * FROM networth_snapshots WHERE user_id=?"
        params: list = [user_id]
        if start_date:
            query += " AND snapshot_date >= ?"
            params.append(start_date)
        query += " ORDER BY snapshot_date DESC LIMIT ?"
        params.append(limit)
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Work expenses & reimbursements (Fase 3)
    # ------------------------------------------------------------------

    def mark_work_expense(
        self,
        tx_id: int,
        status: str = "pending",
        amount: float | None = None,
        notes: str | None = None,
    ) -> int:
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE transactions SET
                    is_work_expense=1,
                    reimbursement_status=?,
                    reimbursement_amount=COALESCE(?,reimbursement_amount),
                    reimbursement_notes=COALESCE(?,reimbursement_notes),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (status, amount, notes, tx_id),
            )
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0]

    def update_reimbursement_status(
        self,
        tx_id: int,
        status: str,
        reimbursement_date: str | None = None,
        amount: float | None = None,
        notes: str | None = None,
    ) -> int:
        with self.get_connection() as conn:
            conn.execute(
                """UPDATE transactions SET
                    reimbursement_status=?,
                    reimbursement_date=COALESCE(?,reimbursement_date),
                    reimbursement_amount=COALESCE(?,reimbursement_amount),
                    reimbursement_notes=COALESCE(?,reimbursement_notes),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (status, reimbursement_date, amount, notes, tx_id),
            )
            conn.commit()
            return conn.execute("SELECT changes()").fetchone()[0]

    def link_reimbursement(
        self,
        reimbursement_tx_id: int,
        expense_tx_id: int,
        allocated_amount: float | None = None,
    ) -> int:
        with self.get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO reimbursement_links
                    (reimbursement_transaction_id, expense_transaction_id, allocated_amount)
                   VALUES (?,?,?)
                   ON CONFLICT(reimbursement_transaction_id, expense_transaction_id)
                   DO UPDATE SET allocated_amount=excluded.allocated_amount""",
                (reimbursement_tx_id, expense_tx_id, allocated_amount),
            )
            conn.commit()
            # Auto-mark expense as reimbursed with today's date
            conn.execute(
                """UPDATE transactions SET
                    reimbursement_status='reimbursed',
                    reimbursement_date=COALESCE(reimbursement_date, date('now')),
                    updated_at=CURRENT_TIMESTAMP
                WHERE id=?""",
                (expense_tx_id,),
            )
            conn.commit()
            return cur.lastrowid

    def unlink_reimbursement(self, reimbursement_tx_id: int, expense_tx_id: int) -> None:
        with self.get_connection() as conn:
            conn.execute(
                "DELETE FROM reimbursement_links WHERE reimbursement_transaction_id=? AND expense_transaction_id=?",
                (reimbursement_tx_id, expense_tx_id),
            )
            # Revert status to submitted if no more links
            cur = conn.execute(
                "SELECT COUNT(*) FROM reimbursement_links WHERE expense_transaction_id=?",
                (expense_tx_id,),
            )
            if cur.fetchone()[0] == 0:
                conn.execute(
                    "UPDATE transactions SET reimbursement_status='submitted', updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (expense_tx_id,),
                )
            conn.commit()

    def get_work_expenses(
        self,
        user_id: int | None = None,
        status: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[dict]:
        query = """
            SELECT t.*, c.name as category_name
            FROM transactions t
            LEFT JOIN categories c ON t.category_id = c.id
            WHERE t.is_work_expense = 1
        """
        params: list = []
        if user_id:
            query += " AND t.user_id = ?"
            params.append(user_id)
        if status:
            query += " AND t.reimbursement_status = ?"
            params.append(status)
        if start_date:
            query += " AND t.transaction_date >= ?"
            params.append(start_date)
        if end_date:
            query += " AND t.transaction_date <= ?"
            params.append(end_date)
        query += " ORDER BY t.transaction_date DESC"
        with self.get_connection() as conn:
            cur = conn.execute(query, params)
            return [dict(r) for r in cur.fetchall()]

    def get_reimbursement_summary(self, user_id: int) -> dict:
        with self.get_connection() as conn:
            cur = conn.execute(
                """SELECT
                    SUM(CASE WHEN reimbursement_status='pending' THEN ABS(amount) ELSE 0 END) as pending_total,
                    SUM(CASE WHEN reimbursement_status='submitted' THEN ABS(amount) ELSE 0 END) as submitted_total,
                    SUM(CASE WHEN reimbursement_status='reimbursed'
                        AND reimbursement_date >= strftime('%Y-01-01','now')
                        THEN COALESCE(reimbursement_amount, ABS(amount)) ELSE 0 END) as reimbursed_ytd,
                    COUNT(CASE WHEN reimbursement_status='pending' THEN 1 END) as pending_count,
                    COUNT(CASE WHEN reimbursement_status='submitted' THEN 1 END) as submitted_count
                FROM transactions
                WHERE user_id=? AND is_work_expense=1""",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else {}

    def get_unlinked_reimbursements(self, user_id: int) -> list[dict]:
        """Return income transactions not yet linked to any expense (potential reimbursement bonuses)."""
        with self.get_connection() as conn:
            cur = conn.execute(
                """SELECT t.* FROM transactions t
                   WHERE t.user_id=? AND t.amount > 0
                   AND NOT EXISTS (
                       SELECT 1 FROM reimbursement_links rl
                       WHERE rl.reimbursement_transaction_id = t.id
                   )
                   ORDER BY t.transaction_date DESC
                   LIMIT 100""",
                (user_id,),
            )
            return [dict(r) for r in cur.fetchall()]

    def get_reimbursement_links(self, reimbursement_tx_id: int) -> list[dict]:
        with self.get_connection() as conn:
            cur = conn.execute(
                """SELECT rl.*, t.transaction_date, t.amount, t.description
                   FROM reimbursement_links rl
                   JOIN transactions t ON rl.expense_transaction_id = t.id
                   WHERE rl.reimbursement_transaction_id=?""",
                (reimbursement_tx_id,),
            )
            return [dict(r) for r in cur.fetchall()]
