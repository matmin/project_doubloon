"""Dark-modern theme injection for Doubloon."""

import streamlit as st

PALETTE = {
    "primary": "#667eea",
    "secondary": "#764ba2",
    "income": "#00c851",
    "expense": "#ff4444",
    "investment": "#4facfe",
    "neutral": "#6c757d",
    "bg_card": "#1e2130",
    "bg_dark": "#161928",
    "text": "#e0e0e0",
    "text_muted": "#8892a4",
    "border": "#2d3555",
}

PLOTLY_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "#1e2130",
        "plot_bgcolor": "#1e2130",
        "font": {"color": "#e0e0e0", "family": "Inter, sans-serif"},
        "colorway": ["#667eea", "#00c851", "#4facfe", "#ff4444", "#ffd700", "#e040fb", "#40e0d0"],
        "xaxis": {"gridcolor": "#2d3555", "zerolinecolor": "#2d3555"},
        "yaxis": {"gridcolor": "#2d3555", "zerolinecolor": "#2d3555"},
        "legend": {"bgcolor": "#1e2130", "bordercolor": "#2d3555"},
        "margin": {"l": 40, "r": 20, "t": 50, "b": 40},
    }
}

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

*, *::before, *::after { box-sizing: border-box; }

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: #161928 !important;
    border-right: 1px solid #2d3555;
}
[data-testid="stSidebar"] * { color: #e0e0e0 !important; }

/* Main background */
[data-testid="stAppViewContainer"] > .main {
    background: #0f1117;
}

/* Header bar */
.doubloon-header {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    padding: 1.2rem 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 4px 24px rgba(102,126,234,0.25);
}
.doubloon-header h1 { color: white; margin: 0; font-size: 1.6rem; font-weight: 700; }
.doubloon-header .subtitle { color: rgba(255,255,255,0.75); font-size: 0.9rem; margin: 0; }

/* KPI cards */
.kpi-card {
    background: #1e2130;
    border: 1px solid #2d3555;
    border-radius: 16px;
    padding: 1.2rem 1.4rem;
    position: relative;
    overflow: hidden;
}
.kpi-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 4px;
    border-radius: 16px 0 0 16px;
}
.kpi-card.income::before  { background: #00c851; }
.kpi-card.expense::before { background: #ff4444; }
.kpi-card.invest::before  { background: #4facfe; }
.kpi-card.neutral::before { background: #667eea; }
.kpi-card.warn::before    { background: #ffd700; }

.kpi-label { color: #8892a4; font-size: 0.78rem; font-weight: 500; text-transform: uppercase; letter-spacing: 0.04em; margin-bottom: 0.3rem; }
.kpi-value { color: #e0e0e0; font-size: 1.6rem; font-weight: 700; line-height: 1; }
.kpi-delta { font-size: 0.78rem; margin-top: 0.3rem; }
.kpi-delta.positive { color: #00c851; }
.kpi-delta.negative { color: #ff4444; }
.kpi-icon { position: absolute; right: 1.2rem; top: 50%; transform: translateY(-50%); font-size: 1.8rem; opacity: 0.25; }

/* Status badges */
.badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.72rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}
.badge-pending    { background: #2d2a1a; color: #ffd700; border: 1px solid #ffd70060; }
.badge-submitted  { background: #1a2040; color: #4facfe; border: 1px solid #4facfe60; }
.badge-reimbursed { background: #0d2a1a; color: #00c851; border: 1px solid #00c85160; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 4px;
    background: #161928;
    border-radius: 12px;
    padding: 4px;
    border: 1px solid #2d3555;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 8px !important;
    color: #8892a4 !important;
    font-weight: 500 !important;
    padding: 0.5rem 1rem !important;
    border: none !important;
    background: transparent !important;
}
.stTabs [aria-selected="true"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    color: white !important;
}

/* Streamlit metric */
[data-testid="stMetric"] { background: #1e2130; border-radius: 12px; padding: 0.8rem; border: 1px solid #2d3555; }
[data-testid="stMetricValue"] { color: #e0e0e0 !important; }
[data-testid="stMetricLabel"] { color: #8892a4 !important; }

/* Buttons */
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #667eea, #764ba2) !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
}
.stButton > button:not([kind="primary"]) {
    background: #1e2130 !important;
    border: 1px solid #2d3555 !important;
    color: #e0e0e0 !important;
    border-radius: 8px !important;
}

/* DataFrames */
.stDataFrame { border-radius: 12px; overflow: hidden; }

/* Progress bar */
.stProgress > div > div { background: linear-gradient(90deg, #667eea, #764ba2) !important; border-radius: 4px; }

/* Divider */
hr { border-color: #2d3555 !important; }

/* Input fields */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stNumberInput > div > div > input,
.stDateInput > div > div > input {
    background: #1e2130 !important;
    border-color: #2d3555 !important;
    color: #e0e0e0 !important;
    border-radius: 8px !important;
}

/* Info / warning boxes */
.stAlert { border-radius: 12px !important; }

/* Success */
.stSuccess { border-left: 4px solid #00c851 !important; background: #0d2a1a !important; }
</style>
"""


def inject_theme() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def header(title: str = "💰 Doubloon", subtitle: str = "") -> None:
    sub_html = f'<p class="subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f'<div class="doubloon-header"><div><h1>{title}</h1>{sub_html}</div></div>',
        unsafe_allow_html=True,
    )


def badge(status: str) -> str:
    cls = {"pending": "badge-pending", "submitted": "badge-submitted", "reimbursed": "badge-reimbursed"}.get(status, "badge-pending")
    labels = {"pending": "In attesa", "submitted": "Inviata", "reimbursed": "Rimborsata"}
    return f'<span class="badge {cls}">{labels.get(status, status)}</span>'
