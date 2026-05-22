"""Doubloon — Personal Finance Platform.

Thin orchestrator: sets up page config, theme, auth, shared services,
then delegates every tab to the matching page module.
"""

import sys
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))

from core.database import DatabaseManager
from dashboard.components.theme import inject_theme
from dashboard.pages import expenses, home, imports, investments, planning, settings
from providers import PROVIDERS, register_all_providers
from services.auth import AuthService
from services.categories import CategoryService
from services.transactions import TransactionFilters, TransactionService

register_all_providers()
_auth = AuthService()
_cat_svc = CategoryService()


# ------------------------------------------------------------------
# Login
# ------------------------------------------------------------------

def _render_login() -> None:
    st.sidebar.title("🔑 Login")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Accedi"):
            session = _auth.authenticate(username, password)
            if session:
                _auth.set_current_user(session)
                st.rerun()
            else:
                st.error("Credenziali non corrette")


def _ensure_user(db: DatabaseManager, display_name: str, email: str) -> None:
    if not db.get_user_by_name(display_name):
        db.create_user(display_name, email)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main() -> None:
    st.set_page_config(
        page_title="Doubloon",
        page_icon="💰",
        layout="wide",
        initial_sidebar_state="expanded",
    )
    inject_theme()

    # Auth gate
    user = _auth.get_current_user()
    if not user:
        st.markdown(
            '<div class="doubloon-header"><h1>💰 Doubloon</h1>'
            '<p class="subtitle">Personal Finance Platform</p></div>',
            unsafe_allow_html=True,
        )
        _render_login()
        st.info("Effettua il login per continuare")
        return

    # Sidebar
    st.sidebar.markdown(
        f'<div style="padding:0.5rem;background:#1e2130;border-radius:10px;border:1px solid #2d3555;margin-bottom:1rem;">'
        f'<div style="color:#8892a4;font-size:0.75rem;">CONNESSO COME</div>'
        f'<div style="color:#e0e0e0;font-weight:700;">👤 {user.display_name}</div></div>',
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🚪 Logout"):
        _auth.set_current_user(None)
        st.rerun()

    # Services
    db = DatabaseManager()
    _ensure_user(db, user.display_name, f"{user.username}@doubloon.local")
    db.setup_default_categories()
    db_user = db.get_user_by_name(user.display_name)
    user_id: int = db_user["id"] if db_user else user.user_id
    tx_svc = TransactionService(db, user_id)

    # Date filters (sidebar)
    st.sidebar.markdown("---")
    st.sidebar.markdown("#### 📅 Periodo")
    today = date.today()
    default_start = date(today.year, today.month, 1)

    c1, c2 = st.sidebar.columns(2)
    with c1:
        if st.button("Mese", help="Questo mese"):
            st.session_state["start_date"] = default_start
            st.session_state["end_date"] = today
    with c2:
        if st.button("30gg", help="Ultimi 30 giorni"):
            d = pd.Timestamp.today() - pd.DateOffset(months=1)
            st.session_state["start_date"] = d.date()
            st.session_state["end_date"] = today

    start = st.sidebar.date_input("Da", value=st.session_state.get("start_date", default_start))
    end = st.sidebar.date_input("A", value=st.session_state.get("end_date", today))
    st.session_state["start_date"] = start
    st.session_state["end_date"] = end
    filters = TransactionFilters(start_date=start, end_date=end)

    # Header
    st.markdown(
        f'<div class="doubloon-header">'
        f'<div><h1>💰 Doubloon</h1></div>'
        f'<div style="color:rgba(255,255,255,0.8);font-size:0.9rem;">'
        f'{start.strftime("%d/%m/%Y")} → {end.strftime("%d/%m/%Y")}</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

    # 7 tabs
    t_home, t_exp, t_inv, t_plan, t_imp, t_set = st.tabs([
        "🏠 Home",
        "💸 Spese",
        "📈 Investimenti",
        "🎯 Pianificazione",
        "📥 Importa",
        "⚙️ Impostazioni",
    ])

    with t_home:
        home.render(db, tx_svc, user_id)

    with t_exp:
        expenses.render(db, tx_svc, filters, user_id, _cat_svc)

    with t_inv:
        investments.render(db, user_id)

    with t_plan:
        planning.render(db, user_id)

    with t_imp:
        imports.render(db, tx_svc, user_id, _cat_svc)

    with t_set:
        settings.render(db, tx_svc, user_id)


if __name__ == "__main__":
    main()
