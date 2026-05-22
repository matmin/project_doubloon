from typing import Any, Dict, Iterable

import pandas as pd

from utils.parsing import parse_amount_smart


class IntesaExcelProvider:
    name = "intesa_excel"
    bank_label = "ISP"

    def _read_with_header_detection(self, file_obj) -> pd.DataFrame:
        expected_tokens = [
            "data",
            "operazione",
            "dettagli",
            "conto o carta",
            "contabilizzazione",
            "categoria",
            "valuta",
            "importo",
        ]
        xls = pd.ExcelFile(file_obj, engine="openpyxl")
        for sheet in xls.sheet_names:
            df_sheet = pd.read_excel(xls, sheet_name=sheet, header=None)
            for i in range(min(100, len(df_sheet))):
                row_vals = [str(v).strip().lower() for v in df_sheet.iloc[i].tolist()]
                matches = 0
                for tok in expected_tokens:
                    if any(tok == v or tok in v for v in row_vals):
                        matches += 1
                if matches >= 3:
                    return pd.read_excel(xls, sheet_name=sheet, header=i)
        try:
            return pd.read_excel(xls, sheet_name=0, header=19)
        except Exception:
            return pd.read_excel(xls, sheet_name=0)

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]:
        df = self._read_with_header_detection(file_obj)
        # normalize expected columns exactly as in the provided list
        rename_map = {}
        for col in df.columns:
            col_clean = str(col).strip().lower()
            if col_clean.startswith("data"):
                rename_map[col] = "Data"
            elif col_clean.startswith("operazione"):
                rename_map[col] = "Operazione"
            elif col_clean.startswith("dettagli"):
                rename_map[col] = "Dettagli"
            elif col_clean.startswith("conto o carta"):
                rename_map[col] = "Conto o carta"
            elif col_clean.startswith("contabilizzazione"):
                rename_map[col] = "Contabilizzazione"
            elif col_clean.startswith("categoria"):
                rename_map[col] = "Categoria"
            elif col_clean.startswith("valuta"):
                rename_map[col] = "Valuta"
            elif "importo" in col_clean:
                rename_map[col] = "Importo"
        df = df.rename(columns=rename_map)

        for _, row in df.iterrows():
            raw_amount = row.get("Importo")
            parsed_amount = parse_amount_smart(raw_amount)
            data = {
                "transaction_date": (
                    pd.to_datetime(row.get("Data"), errors="coerce").date().isoformat()
                    if pd.notna(row.get("Data"))
                    else None
                ),
                "amount": parsed_amount,
                "amount_raw": None if pd.isna(raw_amount) else str(raw_amount),
                "description": str(row.get("Operazione", "")).strip(),
                "detail": str(row.get("Dettagli", "")).strip(),
                "account": str(row.get("Conto o carta", "")).strip(),
                "currency": str(row.get("Valuta", "")).strip(),
                "category_hint": str(row.get("Categoria", "")).strip(),
                "bank": self.bank_label,
                "original": {k: (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items()},
            }
            if data["transaction_date"] and data["amount"] is not None and data["description"]:
                yield data
