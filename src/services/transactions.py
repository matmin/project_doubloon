import json
from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pandas as pd


def _extract_json_field(val: str | None, key: str):
    try:
        js = json.loads(val) if isinstance(val, str) and val else {}
        res = js.get(key)
        return None if res in ("", None) else res
    except Exception:
        return None


@dataclass
class TransactionFilters:
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    limit: int = 2000


class TransactionService:
    def __init__(self, db, user_id: int):
        self._db = db
        self._user_id = user_id

    def get_transactions_df(self, filters: TransactionFilters) -> pd.DataFrame:
        rows = self._db.get_transactions(
            user_id=self._user_id,
            start_date=filters.start_date.isoformat() if filters.start_date else None,
            end_date=filters.end_date.isoformat() if filters.end_date else None,
            limit=filters.limit,
        )
        if not rows:
            return pd.DataFrame()
        return self._normalize_df(pd.DataFrame(rows))

    def update_metadata(self, tx_id: int, **kwargs) -> None:
        self._db.update_transaction_metadata(tx_id, **kwargs)

    def update_classification(self, tx_id: int, **kwargs) -> None:
        self._db.update_transaction_classification(tx_id, **kwargs)

    def _normalize_df(self, df: pd.DataFrame) -> pd.DataFrame:
        if "transaction_date" in df.columns:
            df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
        if "amount" in df.columns:
            df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
        if "original_data" in df.columns:
            for key in ["detail", "category_hint", "account", "currency", "amount_raw"]:
                df[key] = df["original_data"].apply(
                    lambda c, k=key: _extract_json_field(c, k)
                )
        dedup_cols = ["user_name", "transaction_date", "amount", "description"]
        if all(c in df.columns for c in dedup_cols):
            df = df.sort_values("transaction_date").drop_duplicates(
                subset=dedup_cols, keep="last"
            )
        return df
