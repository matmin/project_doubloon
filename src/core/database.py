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
