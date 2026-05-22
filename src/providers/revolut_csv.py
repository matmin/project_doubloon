import csv
import io
from typing import Any, Dict, Iterable

import pandas as pd

from utils.parsing import parse_amount_smart, parse_date_flex


class RevolutCSVProvider:
    name = "revolut_csv"
    bank_label = "Revolut"

    def _read_text(self, file_obj) -> str:
        raw = file_obj.read()
        if isinstance(raw, bytes):
            for enc in ("utf-8-sig", "utf-8", "latin-1"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        return raw

    def _get(self, row: dict, *keys: str) -> str | None:
        lower_map = {k.strip().lower(): v for k, v in row.items() if k}
        for k in keys:
            if k in lower_map and lower_map[k] not in (None, ""):
                return str(lower_map[k]).strip()
        return None

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        text = self._read_text(file_obj)
        reader = csv.DictReader(io.StringIO(text))
        for raw_row in reader:
            row = {k: v for k, v in raw_row.items() if k}
            date_raw = self._get(row, "completed date", "started date", "date")
            tx_date = parse_date_flex(date_raw, ["%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"])
            description = self._get(row, "description", "merchant") or ""
            raw_amount = self._get(row, "amount")
            amount = parse_amount_smart(raw_amount) if raw_amount else None
            fee = parse_amount_smart(self._get(row, "fee") or "") or 0.0
            currency = self._get(row, "currency") or "EUR"
            tx_type_raw = (self._get(row, "type") or "").lower()
            external_id = self._get(row, "id", "reference")
            state = (self._get(row, "state") or "").lower()

            if state and state not in ("completed", "reverted", ""):
                # Skip pending/failed
                continue

            transaction_type = "expense"
            if tx_type_raw in ("transfer", "topup", "exchange"):
                transaction_type = "transfer"

            if not (tx_date and amount is not None and description):
                continue
            yield {
                "transaction_date": tx_date.isoformat(),
                "amount": amount,
                "amount_raw": raw_amount,
                "description": description,
                "detail": tx_type_raw,
                "account": "Revolut",
                "currency": currency,
                "category_hint": "",
                "bank": self.bank_label,
                "source_bank": self.bank_label,
                "external_id": external_id,
                "transaction_type": transaction_type,
                "fee": fee,
                "original": {k: ("" if v is None else str(v)) for k, v in row.items()},
            }


class RevolutInvestExcelProvider:
    name = "revolut_invest_excel"
    bank_label = "Revolut Invest"

    _expected_tokens = ["date", "type", "ticker", "quantity", "price", "total amount"]

    def _read_with_header_detection(self, file_obj) -> pd.DataFrame:
        xls = pd.ExcelFile(file_obj, engine="openpyxl")
        for sheet in xls.sheet_names:
            df_sheet = pd.read_excel(xls, sheet_name=sheet, header=None)
            for i in range(min(50, len(df_sheet))):
                row_vals = [str(v).strip().lower() for v in df_sheet.iloc[i].tolist()]
                matches = sum(
                    1 for tok in self._expected_tokens
                    if any(tok in v for v in row_vals)
                )
                if matches >= 3:
                    return pd.read_excel(xls, sheet_name=sheet, header=i)
        return pd.read_excel(xls, sheet_name=0)

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        df = self._read_with_header_detection(file_obj)
        rename = {}
        for col in df.columns:
            c = str(col).strip().lower()
            if "date" in c and "date" not in rename.values():
                rename[col] = "date"
            elif "type" in c:
                rename[col] = "type"
            elif "ticker" in c or "symbol" in c:
                rename[col] = "ticker"
            elif "isin" in c:
                rename[col] = "isin"
            elif "quantity" in c or "shares" in c:
                rename[col] = "shares"
            elif c == "price":
                rename[col] = "price"
            elif "total amount" in c or c == "amount":
                rename[col] = "amount"
            elif "currency" in c:
                rename[col] = "currency"
            elif "fee" in c:
                rename[col] = "fee"
        df = df.rename(columns=rename)

        for _, row in df.iterrows():
            tx_date = parse_date_flex(row.get("date"))
            raw_amount = row.get("amount")
            amount = parse_amount_smart(raw_amount) if pd.notna(raw_amount) else None
            tx_type_raw = str(row.get("type", "")).strip().lower()
            ticker = str(row.get("ticker", "")).strip() or None
            isin = str(row.get("isin", "")).strip() or None
            shares = parse_amount_smart(row.get("shares")) if pd.notna(row.get("shares")) else None
            price = parse_amount_smart(row.get("price")) if pd.notna(row.get("price")) else None
            fee = parse_amount_smart(row.get("fee")) if pd.notna(row.get("fee")) else 0.0
            currency = str(row.get("currency", "USD")).strip() or "USD"
            description = f"{tx_type_raw.upper()} {ticker or isin or ''}".strip()

            transaction_type = "investment"
            if tx_type_raw in ("deposit", "withdrawal"):
                transaction_type = "transfer"

            if not (tx_date and amount is not None and description):
                continue
            yield {
                "transaction_date": tx_date.isoformat(),
                "amount": amount,
                "amount_raw": None if pd.isna(raw_amount) else str(raw_amount),
                "description": description,
                "detail": tx_type_raw,
                "account": "Revolut Invest",
                "currency": currency,
                "category_hint": "Investimenti",
                "bank": self.bank_label,
                "source_bank": self.bank_label,
                "transaction_type": transaction_type,
                "isin": isin,
                "asset_type": "stock" if ticker else None,
                "shares": shares,
                "price_per_share": price,
                "fee": fee,
                "original": {k: ("" if pd.isna(v) else str(v)) for k, v in row.to_dict().items()},
            }
