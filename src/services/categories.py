from typing import Optional


class CategoryService:
    ALL = ["Necessità", "Extra", "Investimenti", "Trasferimenti"]

    _RULES: list[tuple] = [
        (lambda t: "affitto" in t or "mutuo" in t, "Necessità"),
        (lambda t: "bollett" in t or "enel" in t or "hera" in t, "Necessità"),
        (lambda t: "spesa" in t or "supermerc" in t or "esselunga" in t, "Necessità"),
        (lambda t: "ristor" in t or "bar" in t or "ubereats" in t, "Extra"),
        (lambda t: "shopping" in t or "zara" in t or "amazon" in t, "Extra"),
        (lambda t: "trade republic" in t or "scalable" in t, "Investimenti"),
        (lambda t: "bonifico" in t or "trasfer" in t, "Trasferimenti"),
    ]

    def categorize(
        self,
        description: str,
        detail: Optional[str],
        category_hint: Optional[str],
    ) -> Optional[str]:
        text = f"{description} {detail or ''} {category_hint or ''}".lower()
        for rule_fn, cat in self._RULES:
            if rule_fn(text):
                return cat
        if category_hint:
            for c in self.ALL:
                if c.lower() in category_hint.lower():
                    return c
        return None
