from datetime import date, datetime
from typing import Any, Optional


def parse_amount_smart(x: Any) -> Optional[float]:
    """Parse a number string with mixed thousand/decimal conventions.

    Handles: "1.234,56" (EU), "1,234.56" (US), "1234.56", "1234,56", "-100", "100-".
    Returns None on failure.
    """
    s = str(x).strip()
    if s == "" or s.lower() == "nan":
        return None
    s = s.replace(" ", "").replace(" ", "")
    sign = 1
    if s.startswith("+"):
        s = s[1:]
    if s.startswith("-"):
        sign = -1
        s = s[1:]
    if s.endswith("-"):
        sign *= -1
        s = s[:-1]
    dot_pos = [i for i, ch in enumerate(s) if ch == "."]
    comma_pos = [i for i, ch in enumerate(s) if ch == ","]
    if dot_pos and comma_pos:
        last_dot = dot_pos[-1]
        last_comma = comma_pos[-1]
        dec_index = last_dot if last_dot > last_comma else last_comma
        dec_char = s[dec_index]
        cleaned = []
        for i, ch in enumerate(s):
            if ch in ",." and i != dec_index:
                continue
            cleaned.append(ch)
        s2 = "".join(cleaned)
        if dec_char == ",":
            s2 = s2.replace(",", ".")
    else:
        if dot_pos or comma_pos:
            pos_list = dot_pos or comma_pos
            sep_char = "." if dot_pos else ","
            if len(pos_list) > 1:
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
                if 1 <= digits_after <= 3:
                    s2 = s.replace(",", ".") if sep_char == "," else s
                else:
                    s2 = s.replace(sep_char, "")
        else:
            s2 = s
    try:
        return sign * float(s2)
    except Exception:
        return None


_DEFAULT_DATE_FORMATS = [
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%m/%d/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%d/%m/%y",
]


def parse_date_flex(s: Any, formats: Optional[list[str]] = None) -> Optional[date]:
    """Try multiple date formats, return first match. Returns None on failure."""
    if s is None:
        return None
    if isinstance(s, datetime):
        return s.date()
    if isinstance(s, date):
        return s
    txt = str(s).strip()
    if not txt or txt.lower() in ("nan", "none", "nat"):
        return None
    for fmt in formats or _DEFAULT_DATE_FORMATS:
        try:
            return datetime.strptime(txt, fmt).date()
        except ValueError:
            continue
    return None
