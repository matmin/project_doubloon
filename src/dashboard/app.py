import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.database import DatabaseManager
from providers import PROVIDERS, register_all_providers
from services.auth import AuthService
from services.categories import CategoryService
from services.transactions import TransactionFilters, TransactionService

register_all_providers()

_auth = AuthService()
_cat_svc = CategoryService()


def fmt_eur(value) -> str:
    try:
        v = Decimal(str(value))
    except Exception:
        try:
            v = Decimal(value)
        except Exception:
            return ""
    sign = "-" if v < 0 else ""
    v = abs(v).quantize(Decimal("0.01"))
    parts = str(v).split(".")
    int_part = parts[0]
    frac = parts[1] if len(parts) > 1 else "00"
    groups = []
    while len(int_part) > 3:
        groups.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    groups.insert(0, int_part)
    s = ".".join(groups) + "," + (frac[:2].ljust(2, "0"))
    return f"{sign}€ {s}"


def _render_login():
    st.sidebar.title("Login")
    with st.sidebar.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            session = _auth.authenticate(username, password)
            if session:
                _auth.set_current_user(session)
                st.success(f"Benvenuto {session.display_name}!")
                st.rerun()
            else:
                st.error("Credenziali non corrette")


def _ensure_user(db: DatabaseManager, display_name: str, email: str) -> None:
    if not db.get_user_by_name(display_name):
        db.create_user(display_name, email)


def overview_tab(
    db: DatabaseManager,
    tx_svc: TransactionService,
    filters: TransactionFilters,
):
    df = tx_svc.get_transactions_df(filters)
    if df.empty:
        st.info("📭 Nessuna transazione trovata per il periodo selezionato")
        return

    st.subheader("🔍 Filtri Avanzati")
    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

    categories = (
        sorted([c for c in df["category_name"].dropna().unique()])
        if "category_name" in df.columns
        else []
    )
    selected_cats = col1.multiselect("📂 Categorie", categories, placeholder="Seleziona categorie...")
    search = col2.text_input("🔍 Cerca testo", placeholder="Cerca in descrizione...")
    with col3:
        min_val = st.number_input("Min €", value=0.0, step=1.0)
    with col4:
        max_val = st.number_input("Max €", value=0.0, step=1.0)

    _df = df.copy()
    if selected_cats:
        _df = _df[_df["category_name"].isin(selected_cats)]
    if search:
        mask = _df["description"].str.contains(search, case=False, na=False)
        if "detail" in _df.columns:
            mask = mask | _df["detail"].str.contains(search, case=False, na=False)
        _df = _df[mask]
    if min_val:
        _df = _df[_df["amount"] >= min_val]
    if max_val:
        _df = _df[_df["amount"] <= max_val]

    st.subheader("📊 Indicatori Chiave")
    total_spent = _df[_df["amount"] < 0]["amount"].sum()
    total_income = _df[_df["amount"] > 0]["amount"].sum()
    net = _df["amount"].sum()

    k1, k2, k3, k4 = st.columns(4)
    with k1:
        st.metric("💸 Spesa Totale", fmt_eur(total_spent))
    with k2:
        st.metric("💰 Entrate Totali", fmt_eur(total_income))
    with k3:
        st.metric("📈 Saldo Netto", fmt_eur(net))
    with k4:
        st.metric("📊 Transazioni", f"{len(_df):,}")

    st.subheader("📈 Analisi Grafiche")
    _df["month"] = _df["transaction_date"].dt.to_period("M").dt.to_timestamp()
    trend = _df.groupby(["month", "category_name"], dropna=False)["amount"].sum().reset_index()

    if not trend.empty:
        fig_trend = px.bar(
            trend,
            x="month",
            y="amount",
            color="category_name",
            title="📅 Trend Mensile per Categoria",
            labels={"amount": "Importo (€)", "month": "Mese"},
            color_discrete_sequence=px.colors.qualitative.Set3,
        )
        fig_trend.update_layout(xaxis_title="Mese", yaxis_title="Importo (€)", hovermode="x unified")
        st.plotly_chart(fig_trend, use_container_width=True)

    pie_df = _df[_df["amount"] < 0]
    alloc = pie_df.groupby("category_name", dropna=False)["amount"].sum().abs().reset_index()
    cpie, ctop = st.columns(2)
    if not alloc.empty:
        with cpie:
            fig_pie = px.pie(
                alloc,
                names="category_name",
                values="amount",
                title="🥧 Distribuzione Spese",
                color_discrete_sequence=px.colors.qualitative.Pastel,
            )
            fig_pie.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig_pie, use_container_width=True)
        with ctop:
            top = alloc.sort_values("amount", ascending=False).head(5)
            fig_top = px.bar(
                top,
                x="category_name",
                y="amount",
                title="🏆 Top 5 Categorie",
                labels={"amount": "Importo (€)", "category_name": "Categoria"},
                color="amount",
                color_continuous_scale="Blues",
            )
            fig_top.update_layout(xaxis_title="Categoria", yaxis_title="Importo (€)", showlegend=False)
            st.plotly_chart(fig_top, use_container_width=True)

    st.subheader("🕒 Transazioni Recenti")
    recent = _df.sort_values("transaction_date", ascending=False).head(20).copy()
    if not recent.empty:
        recent["amount_formatted"] = recent["amount"].apply(fmt_eur)
        recent["Data"] = recent["transaction_date"].dt.strftime("%d/%m/%Y")
        col_map = {
            "Data": "Data",
            "description": "Descrizione",
            "amount_formatted": "Importo",
            "category_name": "Categoria",
            "account": "Conto",
        }
        show = [c for c in col_map if col_map[c] in recent.columns or c in recent.columns]
        display_cols = [c for c in col_map if c in recent.columns]
        st.dataframe(recent[display_cols], use_container_width=True, hide_index=True)
    else:
        st.info("📭 Nessuna transazione recente trovata")


def transactions_tab(
    db: DatabaseManager,
    tx_svc: TransactionService,
    filters: TransactionFilters,
):
    df = tx_svc.get_transactions_df(filters)
    if df.empty:
        st.info("Nessuna transazione")
        return

    st.subheader("📊 Tutte le Transazioni")
    df_display = df.sort_values("transaction_date", ascending=False).copy()
    df_display["amount_formatted"] = df_display["amount"].apply(fmt_eur)
    df_display["Data"] = df_display["transaction_date"].dt.strftime("%d/%m/%Y")

    display_cols = [
        c for c in ["Data", "description", "amount_formatted", "category_name", "account", "detail"]
        if c in df_display.columns
    ]
    st.dataframe(df_display[display_cols], use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("📝 Modifica Categoria")

    df_select = df.sort_values("transaction_date", ascending=False).copy()
    df_select["amount_formatted"] = df_select["amount"].apply(fmt_eur)
    selected_idx = st.selectbox(
        "Seleziona transazione:",
        range(len(df_select)),
        format_func=lambda x: (
            f"{df_select.iloc[x]['transaction_date'].strftime('%Y-%m-%d')} — "
            f"{df_select.iloc[x]['description']} — "
            f"{df_select.iloc[x]['amount_formatted']}"
        ),
    )

    if selected_idx is not None:
        selected_tx = df_select.iloc[selected_idx]
        current_cat = selected_tx.get("category_name")
        new_cat = st.selectbox(
            "Categoria",
            [None] + _cat_svc.ALL,
            index=([None] + _cat_svc.ALL).index(current_cat) if current_cat in _cat_svc.ALL else 0,
            format_func=lambda x: x or "— nessuna —",
        )
        if st.button("💾 Salva categoria", key="save_cat"):
            if new_cat:
                existing = db.get_category_by_name(new_cat)
                if existing:
                    tx_svc.update_classification(int(selected_tx["id"]), category_id=existing["id"])
                    st.success("✅ Categoria aggiornata!")
                    st.rerun()


def settings_tab(db: DatabaseManager, tx_svc: TransactionService):
    st.header("📥 Carica Dati")
    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Importa da provider")
        provider_name = st.selectbox("Provider", list(PROVIDERS.keys()))
        f = st.file_uploader("Seleziona file (CSV/XLSX)", type=["csv", "xlsx"])

        if f:
            preview = list(PROVIDERS[provider_name].parse(f))
            for t in preview:
                t["category_suggested"] = _cat_svc.categorize(
                    t.get("description", ""), t.get("detail"), t.get("category_hint")
                )
            prev_df = pd.DataFrame(preview[:10])
            if not prev_df.empty and "amount" in prev_df.columns:
                prev_df["amount_formatted"] = prev_df["amount"].apply(fmt_eur)
            st.write("**Anteprima (prime 10):**")
            st.dataframe(prev_df, use_container_width=True)
            f.seek(0)

        if f and st.button("🚀 Importa in DB", type="primary"):
            provider = PROVIDERS[provider_name]
            inserted = 0
            for t in provider.parse(f):
                bank = getattr(provider, "bank_label", provider_name)
                cat = _cat_svc.categorize(
                    t.get("description", ""), t.get("detail"), t.get("category_hint")
                )
                created, tx_id = db.upsert_transaction_if_new(
                    tx_svc._user_id,
                    t["transaction_date"],
                    t["amount"],
                    t["description"],
                )
                if created:
                    inserted += 1
                if tx_id:
                    meta = {
                        "source": provider_name,
                        "bank": bank,
                        "detail": t.get("detail", ""),
                        "category_hint": t.get("category_hint", ""),
                        "category_suggested": cat,
                        "original": t.get("original", {}),
                        "amount_raw": t.get("amount_raw"),
                        "account": t.get("account"),
                        "currency": t.get("currency"),
                    }
                    tx_svc.update_metadata(
                        tx_id,
                        import_source=provider_name,
                        original_data=json.dumps(meta, ensure_ascii=False),
                        payee=t["description"],
                        notes=meta["detail"] or None,
                    )
                    if cat:
                        existing = db.get_category_by_name(cat)
                        if existing:
                            tx_svc.update_classification(tx_id, category_id=existing["id"])
            st.success(f"✅ Import completato: {inserted} nuove transazioni.")
            st.rerun()

    with col2:
        st.subheader("⚙️ Gestione Database")

        if st.button("🗑️ Reset Database", type="secondary"):
            st.session_state["show_reset_confirm"] = True

        if st.session_state.get("show_reset_confirm", False):
            st.warning("⚠️ **ATTENZIONE: Questa operazione cancellerà TUTTI i dati!**")
            confirm_text = st.text_input("Digita 'CONFERMA' per procedere:")
            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Sì, cancella tutto", type="primary"):
                    if confirm_text == "CONFERMA":
                        db.reset_database()
                        st.success("🗑️ Database resettato!")
                        st.session_state["show_reset_confirm"] = False
                        st.rerun()
                    else:
                        st.error("Testo di conferma non corretto")
            with col_no:
                if st.button("❌ Annulla"):
                    st.session_state["show_reset_confirm"] = False
                    st.rerun()

        st.subheader("📊 Statistiche")
        total_tx = len(db.get_transactions(limit=10000))
        total_users = len(db.get_all_users())
        st.metric("Transazioni totali", total_tx)
        st.metric("Utenti", total_users)

        st.subheader("🔧 Azioni Rapide")
        if st.button("🔄 Ricarica categorie"):
            db.setup_default_categories()
            st.success("✅ Categorie ricaricate!")


def main():
    st.set_page_config(
        page_title="Doubloon", page_icon="💰", layout="wide", initial_sidebar_state="expanded"
    )

    st.markdown(
        """
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem; border-radius: 10px; color: white;
        text-align: center; margin-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 2px; }
    .stTabs [data-baseweb="tab"] { height: 50px; padding-left: 20px; padding-right: 20px; }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-header"><h1>💰 Doubloon — Finance Tracker</h1></div>',
        unsafe_allow_html=True,
    )

    user = _auth.get_current_user()
    if not user:
        _render_login()
        st.info("Effettua il login per continuare")
        return

    st.sidebar.markdown(f"👤 **{user.display_name}**")
    if st.sidebar.button("Logout"):
        _auth.set_current_user(None)
        st.rerun()

    db = DatabaseManager()
    _ensure_user(db, user.display_name, f"{user.username}@example.com")
    db.setup_default_categories()

    tx_svc = TransactionService(db, user.user_id)

    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Filtri Temporali")
    today = pd.Timestamp.today().date()
    default_start = date(today.year, today.month, 1)

    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("📅 Questo mese"):
            st.session_state["start_date"] = default_start
            st.session_state["end_date"] = today
    with col2:
        if st.button("📅 Ultimi 30gg"):
            prev = date(today.year, today.month - 1, today.day) if today.month > 1 else date(today.year - 1, 12, today.day)
            st.session_state["start_date"] = prev
            st.session_state["end_date"] = today

    start = st.sidebar.date_input("📅 Da", value=st.session_state.get("start_date", default_start), key="start_date_picker")
    end = st.sidebar.date_input("📅 A", value=st.session_state.get("end_date", today), key="end_date_picker")
    st.session_state["start_date"] = start
    st.session_state["end_date"] = end

    filters = TransactionFilters(start_date=start, end_date=end)

    tab_overview, tab_tx, tab_settings = st.tabs(["📊 Overview", "📝 Transazioni", "⚙️ Impostazioni"])
    with tab_overview:
        overview_tab(db, tx_svc, filters)
    with tab_tx:
        transactions_tab(db, tx_svc, filters)
    with tab_settings:
        settings_tab(db, tx_svc)


if __name__ == "__main__":
    main()
