"""Reusable Plotly chart builders with the Doubloon dark theme."""

import plotly.express as px
import plotly.graph_objects as go
import pandas as pd

from .theme import PALETTE, PLOTLY_TEMPLATE

_COLORS = list(PLOTLY_TEMPLATE["layout"]["colorway"])


def _apply(fig: go.Figure) -> go.Figure:
    fig.update_layout(**PLOTLY_TEMPLATE["layout"])
    return fig


def bar_monthly(df: pd.DataFrame, x: str, y: str, color: str | None = None, title: str = "") -> go.Figure:
    fig = px.bar(df, x=x, y=y, color=color, title=title,
                 color_discrete_sequence=_COLORS,
                 barmode="stack")
    return _apply(fig)


def pie_allocation(df: pd.DataFrame, names: str, values: str, title: str = "") -> go.Figure:
    fig = px.pie(df, names=names, values=values, title=title,
                 color_discrete_sequence=_COLORS, hole=0.45)
    fig.update_traces(textposition="inside", textinfo="percent+label",
                      marker=dict(line=dict(color="#0f1117", width=2)))
    return _apply(fig)


def line_trend(df: pd.DataFrame, x: str, y: str | list[str], title: str = "") -> go.Figure:
    if isinstance(y, list):
        fig = go.Figure()
        for col, color in zip(y, _COLORS):
            fig.add_trace(go.Scatter(x=df[x], y=df[col], name=col, line=dict(color=color, width=2)))
        fig.update_layout(title=title)
    else:
        fig = px.line(df, x=x, y=y, title=title, color_discrete_sequence=_COLORS)
    return _apply(fig)


def monte_carlo_fan(mc_df: pd.DataFrame, title: str = "Proiezione Monte Carlo") -> go.Figure:
    """Fan chart from ScenarioRunner.run_monte_carlo() output (columns: year, p10-p90)."""
    fig = go.Figure()
    fill_pairs = [("p10", "p90", "rgba(102,126,234,0.10)"),
                  ("p25", "p75", "rgba(102,126,234,0.18)")]
    for lo, hi, fill in fill_pairs:
        fig.add_trace(go.Scatter(
            x=list(mc_df["year"]) + list(mc_df["year"])[::-1],
            y=list(mc_df[hi]) + list(mc_df[lo])[::-1],
            fill="toself", fillcolor=fill,
            line=dict(color="rgba(0,0,0,0)"),
            showlegend=False,
        ))
    fig.add_trace(go.Scatter(
        x=mc_df["year"], y=mc_df["p50"],
        name="Mediana (p50)", line=dict(color=PALETTE["primary"], width=2.5),
    ))
    fig.update_layout(title=title, xaxis_title="Anno", yaxis_title="Patrimonio netto (€)")
    return _apply(fig)


def amortization_chart(df: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["month"], y=df["principal"], name="Capitale",
                         marker_color=PALETTE["income"]))
    fig.add_trace(go.Bar(x=df["month"], y=df["interest"], name="Interessi",
                         marker_color=PALETTE["expense"]))
    fig.update_layout(barmode="stack", title="Piano di ammortamento",
                      xaxis_title="Mese", yaxis_title="€")
    return _apply(fig)


def pnl_bar(df: pd.DataFrame, title: str = "P&L per transazione") -> go.Figure:
    if df.empty:
        return go.Figure()
    colors = [PALETTE["income"] if v >= 0 else PALETTE["expense"] for v in df["net_pnl"]]
    fig = go.Figure(go.Bar(
        x=df["description"],
        y=df["net_pnl"],
        marker_color=colors,
    ))
    fig.update_layout(title=title, xaxis_title="Asset", yaxis_title="P&L netto (€)")
    return _apply(fig)


def benchmark_line(df: pd.DataFrame) -> go.Figure:
    """Indexed-to-100 comparison chart from BenchmarkService."""
    if df is None or df.empty:
        return go.Figure()
    fig = go.Figure()
    date_col = "date" if "date" in df.columns else df.columns[0]
    for col, color in zip([c for c in df.columns if c != date_col], _COLORS):
        fig.add_trace(go.Scatter(
            x=df[date_col], y=df[col], name=col,
            line=dict(color=color, width=2),
        ))
    fig.update_layout(title="Portafoglio vs Benchmark (base 100)",
                      xaxis_title="Data", yaxis_title="Valore indicizzato")
    return _apply(fig)
