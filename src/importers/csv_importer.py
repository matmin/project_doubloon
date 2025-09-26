import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..core.database import DatabaseManager

logger = logging.getLogger(__name__)


class CSVImporter:
    def __init__(self, db_manager=None):
        self.db = db_manager or DatabaseManager()
        self.bank_configs = self._load_bank_configs()

    def _load_bank_configs(self):
        import json

        config_path = Path(__file__).parent.parent.parent / "config" / "bank_configs.json"
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def import_csv(self, file_path: str, bank_code: str, user_id: int):
        if bank_code not in self.bank_configs["banks"]:
            raise ValueError(f"Banca {bank_code} non configurata")
        config = self.bank_configs["banks"][bank_code]

        df = pd.read_csv(file_path, delimiter=config["csv_delimiter"], encoding=config["encoding"])

        inserted = 0
        for _, row in df.iterrows():
            # Normalizza e salva transazione
            date_str = str(row[config["columns_mapping"]["date"]]).strip()
            try:
                dt = datetime.strptime(date_str, config.get("date_format", "%Y-%m-%d")).date()
            except Exception:
                try:
                    dt = pd.to_datetime(date_str).date()
                except Exception:
                    logger.warning(f"Data non parsabile: {date_str}")
                    continue
            amount_raw = str(row[config["columns_mapping"]["amount"]])
            amount = (
                float(amount_raw.replace(".", "").replace(",", "."))
                if "," in amount_raw
                else float(amount_raw)
            )
            description = str(row[config["columns_mapping"]["description"]])

            created, _ = self.db.upsert_transaction_if_new(
                user_id,
                dt.isoformat(),
                amount,
                description,
            )
            if created:
                inserted += 1
        logger.info(f"Importazioni CSV completate: {inserted}")
        return inserted
