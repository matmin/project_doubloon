import csv
import io
from typing import Any, Dict, Iterable

from utils.parsing import parse_amount_smart, parse_date_flex

_INVESTMENT_ASSET_TYPES = {"etf", "stock", "bond", "crypto", "derivative", "fund"}


class ScalableCSVProvider:
    name = "scalable_csv"
    bank_label = "Scalable"

    _delimiter = ";"

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

    def _detect_delimiter(self, text: str) -> str:
        sample = text[:2048]
        if sample.count(";") > sample.count(","):
            return ";"
        return ","

    def _get(self, row: dict, *keys: str) -> str | None:
        lower_map = {k.strip().lower(): v for k, v in row.items() if k}
        for k in keys:
            if k in lower_map and lower_map[k] not in (None, ""):
                return str(lower_map[k]).strip()
        return None

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        text = self._read_text(file_obj)
        delim = self._detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        for raw_row in reader:
            row = {k: v for k, v in raw_row.items() if k}
            tx_date = parse_date_flex(
                self._get(row, "date", "datum"), ["%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y"]
            )
            description = self._get(row, "description", "beschreibung", "name") or ""
            asset_type = (self._get(row, "assettype", "asset_type") or "").lower()
            tx_type_raw = (self._get(row, "type", "transaktionstyp") or "").lower()
            raw_amount = self._get(row, "amount", "betrag", "total")
            amount = parse_amount_smart(raw_amount) if raw_amount else None
            isin = self._get(row, "isin")
            shares = parse_amount_smart(self._get(row, "shares", "stueck") or "")
            price = parse_amount_smart(self._get(row, "price", "kurs") or "")
            fee = parse_amount_smart(self._get(row, "fee", "gebuehr") or "") or 0.0
            tax = parse_amount_smart(self._get(row, "tax", "steuer") or "") or 0.0
            currency = self._get(row, "currency", "waehrung") or "EUR"
            external_id = self._get(row, "reference", "id")

            is_investment = asset_type in _INVESTMENT_ASSET_TYPES or bool(isin)
            transaction_type = "investment" if is_investment else "expense"
            if "deposit" in tx_type_raw or "einzahlung" in tx_type_raw:
                transaction_type = "transfer"

            if not (tx_date and amount is not None and description):
                continue
            yield {
                "transaction_date": tx_date.isoformat(),
                "amount": amount,
                "amount_raw": raw_amount,
                "description": description,
                "detail": tx_type_raw,
                "account": "Scalable",
                "currency": currency,
                "category_hint": asset_type,
                "bank": self.bank_label,
                "source_bank": self.bank_label,
                "external_id": external_id,
                "transaction_type": transaction_type,
                "isin": isin,
                "asset_type": asset_type or None,
                "shares": shares,
                "price_per_share": price,
                "fee": fee,
                "tax": tax,
                "original": {k: ("" if v is None else str(v)) for k, v in row.items()},
            }
