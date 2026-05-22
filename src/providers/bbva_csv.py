import csv
import io
from typing import Any, Dict, Iterable

from utils.parsing import parse_amount_smart, parse_date_flex


class BBVACSVProvider:
    name = "bbva_csv"
    bank_label = "BBVA"

    _DATE_KEYS = ["fecha", "data", "date", "fecha operacion", "fecha valor"]
    _DESC_KEYS = ["concepto", "descrizione", "description", "concepto operacion", "movimiento"]
    _AMOUNT_KEYS = ["importe", "importo", "amount", "monto"]
    _BALANCE_KEYS = ["saldo", "balance"]

    def _read_text(self, file_obj) -> str:
        raw = file_obj.read()
        if isinstance(raw, bytes):
            for enc in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
                try:
                    return raw.decode(enc)
                except UnicodeDecodeError:
                    continue
            return raw.decode("utf-8", errors="replace")
        return raw

    def _detect_delimiter(self, text: str) -> str:
        sample = "\n".join(text.splitlines()[:5])
        counts = {sep: sample.count(sep) for sep in [";", ",", "\t", "|"]}
        return max(counts, key=counts.get) or ","

    def _fuzzy_get(self, row: dict, keys: list[str]) -> str | None:
        lower_map = {k.strip().lower(): v for k, v in row.items() if k}
        for k in keys:
            if k in lower_map and lower_map[k] not in (None, ""):
                return str(lower_map[k]).strip()
        # partial match fallback
        for k in keys:
            for col_lower, v in lower_map.items():
                if k in col_lower and v not in (None, ""):
                    return str(v).strip()
        return None

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        text = self._read_text(file_obj)
        # BBVA exports may have preamble rows before headers; skip until row has expected keys
        lines = text.splitlines()
        header_idx = 0
        for i, line in enumerate(lines[:20]):
            low = line.lower()
            if any(k in low for k in ["fecha", "concepto", "importe"]):
                header_idx = i
                break
        text = "\n".join(lines[header_idx:])

        delim = self._detect_delimiter(text)
        reader = csv.DictReader(io.StringIO(text), delimiter=delim)
        for raw_row in reader:
            row = {k: v for k, v in raw_row.items() if k}
            date_raw = self._fuzzy_get(row, self._DATE_KEYS)
            tx_date = parse_date_flex(
                date_raw, ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]
            )
            description = self._fuzzy_get(row, self._DESC_KEYS) or ""
            raw_amount = self._fuzzy_get(row, self._AMOUNT_KEYS)
            amount = parse_amount_smart(raw_amount) if raw_amount else None

            if not (tx_date and amount is not None and description):
                continue
            yield {
                "transaction_date": tx_date.isoformat(),
                "amount": amount,
                "amount_raw": raw_amount,
                "description": description,
                "detail": "",
                "account": "BBVA",
                "currency": "EUR",
                "category_hint": "",
                "bank": self.bank_label,
                "source_bank": self.bank_label,
                "transaction_type": "expense" if amount < 0 else "income",
                "original": {k: ("" if v is None else str(v)) for k, v in row.items()},
            }
