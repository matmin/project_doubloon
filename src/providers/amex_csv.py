import csv
import io
from typing import Any, Dict, Iterable

from utils.parsing import parse_amount_smart, parse_date_flex


class AmexCSVProvider:
    name = "amex_csv"
    bank_label = "Amex"

    _DATE_KEYS = ["date"]
    _DESC_KEYS = ["description", "merchant"]
    _AMOUNT_KEYS = ["amount"]
    _REF_KEYS = ["reference"]
    _CATEGORY_KEYS = ["category"]
    _DETAIL_KEYS = ["extended details", "appears on statement as"]

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

    def _fuzzy_get(self, row: dict, keys: list[str]) -> str | None:
        lower_map = {k.strip().lower(): v for k, v in row.items() if k}
        for k in keys:
            if k in lower_map:
                v = lower_map[k]
                return str(v).strip() if v is not None else None
        return None

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        text = self._read_text(file_obj)
        reader = csv.DictReader(io.StringIO(text))
        for raw_row in reader:
            row = {k: v for k, v in raw_row.items() if k}
            raw_amount = self._fuzzy_get(row, self._AMOUNT_KEYS)
            parsed = parse_amount_smart(raw_amount) if raw_amount is not None else None
            # Amex CSVs: positive amounts = spending → invert sign
            amount = -abs(parsed) if parsed is not None else None
            date_raw = self._fuzzy_get(row, self._DATE_KEYS)
            tx_date = parse_date_flex(date_raw, ["%d/%m/%Y", "%m/%d/%Y", "%Y-%m-%d"])
            description = self._fuzzy_get(row, self._DESC_KEYS) or ""
            detail = self._fuzzy_get(row, self._DETAIL_KEYS)
            category_hint = self._fuzzy_get(row, self._CATEGORY_KEYS)
            external_id = self._fuzzy_get(row, self._REF_KEYS)

            if not (tx_date and amount is not None and description):
                continue
            yield {
                "transaction_date": tx_date.isoformat(),
                "amount": amount,
                "amount_raw": raw_amount,
                "description": description,
                "detail": detail or "",
                "account": "Amex",
                "currency": "EUR",
                "category_hint": category_hint or "",
                "bank": self.bank_label,
                "source_bank": self.bank_label,
                "external_id": external_id,
                "transaction_type": "expense",
                "original": {k: ("" if v is None else str(v)) for k, v in row.items()},
            }
