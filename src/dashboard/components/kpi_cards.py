"""Reusable KPI card components."""

from decimal import Decimal
from typing import Optional

import streamlit as st


def fmt_eur(value, show_sign: bool = False) -> str:
    try:
        v = Decimal(str(value))
    except Exception:
        return "—"
    sign = ""
    if show_sign:
        sign = "+" if v > 0 else ""
    elif v < 0:
        sign = "-"
    v_abs = abs(v).quantize(Decimal("0.01"))
    parts = str(v_abs).split(".")
    int_part = parts[0]
    frac = parts[1] if len(parts) > 1 else "00"
    groups: list[str] = []
    while len(int_part) > 3:
        groups.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    groups.insert(0, int_part)
    return f"{sign}€ {'.'.join(groups)},{frac[:2].ljust(2, '0')}"


def kpi_card(
    label: str,
    value: str,
    icon: str = "",
    variant: str = "neutral",
    delta: Optional[str] = None,
    delta_positive: Optional[bool] = None,
) -> None:
    delta_html = ""
    if delta is not None:
        cls = "positive" if delta_positive else "negative"
        delta_html = f'<div class="kpi-delta {cls}">{delta}</div>'
    icon_html = f'<div class="kpi-icon">{icon}</div>' if icon else ""
    st.markdown(
        f"""
        <div class="kpi-card {variant}">
            {icon_html}
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def kpi_row(cards: list[dict]) -> None:
    """Render a row of KPI cards.

    Each card dict: label, value, icon?, variant?, delta?, delta_positive?
    """
    cols = st.columns(len(cards))
    for col, card in zip(cols, cards):
        with col:
            kpi_card(**card)
    st.markdown("<br>", unsafe_allow_html=True)
