from typing import Any, Dict, Iterable

import pandas as pd


class IntesaExcelProvider:
    name = "intesa_excel"

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

    @staticmethod
    def _parse_amount_smart(x):
        s = str(x).strip()
        if s == "" or s.lower() == "nan":
            return None
        # normalize spaces and sign
        s = s.replace("\u00A0", "").replace(" ", "")
        sign = 1
        if s.startswith("+"):
            s = s[1:]
        if s.startswith("-"):
            sign = -1
            s = s[1:]
        if s.endswith("-"):
            sign *= -1
            s = s[:-1]
        # find separators
        dot_pos = [i for i, ch in enumerate(s) if ch == "."]
        comma_pos = [i for i, ch in enumerate(s) if ch == ","]
        if dot_pos and comma_pos:
            # rightmost separator is decimal
            last_dot = dot_pos[-1]
            last_comma = comma_pos[-1]
            dec_index = last_dot if last_dot > last_comma else last_comma
            dec_char = s[dec_index]
            # remove all other separators except the decimal one
            cleaned = []
            for i, ch in enumerate(s):
                if ch in ",." and i != dec_index:
                    continue
                cleaned.append(ch)
            s2 = "".join(cleaned)
            if dec_char == ",":
                s2 = s2.replace(",", ".")
            # else dec_char == '.' already dot
        else:
            # only one kind of separator or none
            if dot_pos or comma_pos:
                pos_list = dot_pos or comma_pos
                sep_char = "." if dot_pos else ","
                if len(pos_list) > 1:
                    # multiple same separators: last is decimal, others thousands
                    last = pos_list[-1]
                    cleaned = []
                    for i, ch in enumerate(s):
                        if ch == sep_char and i != last:
                            continue
                        cleaned.append(ch)
                    s2 = "".join(cleaned)
                    if sep_char == ",":
                        s2 = s2.replace(",", ".")
                else:
                    idx = pos_list[0]
                    digits_after = len(s) - idx - 1
                    # treat as decimal if there are 1-3 digits after; else treat as thousands
                    if 1 <= digits_after <= 3:
                        s2 = s.replace(",", ".") if sep_char == "," else s
                    else:
                        # thousands separator only
                        s2 = s.replace(sep_char, "")
            else:
                s2 = s
        try:
            return sign * float(s2)
        except Exception:
            return None

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
            parsed_amount = self._parse_amount_smart(raw_amount)
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
                "original": {k: (None if pd.isna(v) else str(v)) for k, v in row.to_dict().items()},
            }
            if data["transaction_date"] and data["amount"] is not None and data["description"]:
                yield data
