import json
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# Ensure project src is on path when running via Streamlit
sys.path.append(str(Path(__file__).resolve().parents[1]))
from core.database import DatabaseManager
from providers.base import PROVIDERS, register_provider
from providers.intesa_excel import IntesaExcelProvider

register_provider(IntesaExcelProvider())

USERS = {"matteo": "password1", "paola": "password2"}
VIEW_TO_USER = {"Matteo": "matteo", "Paola": "paola", "Nostra": None}
CATEGORIES = [
    "Necessità",
    "Extra",
    "Investimenti",
    "Trasferimenti",
]


def _extract_json_field(val: str | None, key: str):
    try:
        js = json.loads(val) if isinstance(val, str) and val else {}
        res = js.get(key)
        return None if res in ("", None) else res
    except Exception:
        return None


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


def login():
    st.sidebar.title("Login")
    if "username" not in st.session_state:
        st.session_state["username"] = None
    with st.sidebar.form("login_form"):
        username = st.text_input("Username", value=st.session_state.get("username_input", ""))
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            st.session_state["username_input"] = username
            if username.lower() in USERS and USERS[username.lower()] == password:
                st.session_state["username"] = username.lower()
                st.success(f"Benvenuto {username.capitalize()}!")
            else:
                st.error("Credenziali non corrette")
    return st.session_state.get("username", None)


def ensure_users(db: DatabaseManager):
    if not db.get_user_by_name("Matteo"):
        db.create_user("Matteo", "matteo@example.com")
    if not db.get_user_by_name("Paola"):
        db.create_user("Paola", "paola@example.com")


def user_toggle():
    st.sidebar.header("Vista")
    view = st.sidebar.radio("Seleziona vista", list(VIEW_TO_USER.keys()))
    st.session_state["view"] = view
    return view


def categorize_row(description: str, detail: str | None, category_hint: str | None) -> str | None:
    text = f"{description} {detail or ''} {category_hint or ''}".lower()
    rules = [
        ("affitto" in text or "mutuo" in text, "Necessità"),
        ("bollett" in text or "enel" in text or "hera" in text, "Necessità"),
        ("spesa" in text or "supermerc" in text or "esselunga" in text, "Necessità"),
        ("ristor" in text or "bar" in text or "ubereats" in text, "Extra"),
        ("shopping" in text or "zara" in text or "amazon" in text, "Extra"),
        ("trade republic" in text or "scalable" in text, "Investimenti"),
        ("bonifico" in text or "trasfer" in text, "Trasferimenti"),
    ]
    for cond, cat in rules:
        if cond:
            return cat
    if category_hint:
        for c in CATEGORIES:
            if c.lower() in category_hint.lower():
                return c
    return None


def load_transactions_df(
    db: DatabaseManager, view: str, start: date | None = None, end: date | None = None
):
    user_key = VIEW_TO_USER[view]
    if user_key is None:
        rows = db.get_transactions(
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
            limit=2000,
        )
    else:
        user = db.get_user_by_name(user_key.capitalize())
        rows = db.get_transactions(
            user_id=user["id"],
            start_date=start.isoformat() if start else None,
            end_date=end.isoformat() if end else None,
            limit=2000,
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Normalize types
    if "transaction_date" in df.columns:
        df["transaction_date"] = pd.to_datetime(df["transaction_date"], errors="coerce")
    if "amount" in df.columns:
        df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    if "original_data" in df.columns:
        for key, out in [
            ("detail", "detail"),
            ("category_hint", "category_hint"),
            ("account", "account"),
            ("currency", "currency"),
            ("amount_raw", "amount_raw"),
        ]:
            df[out] = df["original_data"].apply(lambda c, k=key: _extract_json_field(c, k))
    # Deduplicate on normalized key
    for col in ["user_name", "transaction_date", "amount", "description"]:
        if col not in df.columns:
            return df
    df = df.sort_values("transaction_date").drop_duplicates(
        subset=["user_name", "transaction_date", "amount", "description"], keep="last"
    )
    return df


def overview_tab(db: DatabaseManager, view: str, start: date | None, end: date | None):
    df = load_transactions_df(db, view, start, end)
    if df.empty:
        st.info("📭 Nessuna transazione trovata per il periodo selezionato")
        return

    # Enhanced filters with better UX
    st.subheader("🔍 Filtri Avanzati")

    col1, col2, col3, col4 = st.columns([2, 2, 1, 1])

    categories = (
        sorted([c for c in df["category_name"].dropna().unique()])
        if "category_name" in df.columns
        else []
    )
    selected_cats = col1.multiselect(
        "📂 Categorie", categories, placeholder="Seleziona categorie..."
    )
    search = col2.text_input("🔍 Cerca testo", placeholder="Cerca in descrizione...")

    with col3:
        min_val = st.number_input("Min €", value=0.0, step=1.0, help="Importo minimo")
    with col4:
        max_val = st.number_input("Max €", value=0.0, step=1.0, help="Importo massimo")
    # Apply filters
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

    # Enhanced KPIs with better formatting
    st.subheader("📊 Indicatori Chiave")

    total_spent = _df[_df["amount"] < 0]["amount"].sum()
    total_income = _df[_df["amount"] > 0]["amount"].sum()
    net = _df["amount"].sum()

    # Calculate additional metrics
    transaction_count = len(_df)

    k1, k2, k3, k4 = st.columns(4)

    with k1:
        st.metric("💸 Spesa Totale", fmt_eur(total_spent), help="Somma di tutte le uscite")
    with k2:
        st.metric("💰 Entrate Totali", fmt_eur(total_income), help="Somma di tutte le entrate")
    with k3:
        st.metric(
            "📈 Saldo Netto",
            fmt_eur(net),
            delta=fmt_eur(net - total_spent) if net != total_spent else None,
            help="Differenza tra entrate e uscite",
        )
    with k4:
        st.metric("📊 Transazioni", f"{transaction_count:,}", help="Numero totale di transazioni")

    # Enhanced charts with better styling
    st.subheader("📈 Analisi Grafiche")

    # Monthly trend chart
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
        fig_trend.update_layout(
            xaxis_title="Mese",
            yaxis_title="Importo (€)",
            legend_title="Categoria",
            hovermode="x unified",
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    # Pie chart and top categories
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
            fig_top.update_layout(
                xaxis_title="Categoria", yaxis_title="Importo (€)", showlegend=False
            )
            st.plotly_chart(fig_top, use_container_width=True)

    # Enhanced recent transactions panel
    st.subheader("🕒 Transazioni Recenti")
    recent = _df.sort_values("transaction_date", ascending=False).head(20).copy()

    if not recent.empty:
        # Format for display
        recent_display = recent.copy()
        if "amount" in recent_display.columns:
            recent_display["amount_formatted"] = recent_display["amount"].apply(fmt_eur)
        if "transaction_date" in recent_display.columns:
            recent_display["Data"] = recent_display["transaction_date"].dt.strftime("%d/%m/%Y")

        # Select columns for display
        display_cols = []
        col_mapping = {
            "Data": "Data",
            "user_name": "Utente",
            "description": "Descrizione",
            "amount_formatted": "Importo",
            "category_name": "Categoria",
            "account": "Conto",
        }

        for display_name, col_name in col_mapping.items():
            if col_name in recent_display.columns:
                display_cols.append(display_name)

        if display_cols:
            st.dataframe(recent_display[display_cols], use_container_width=True, hide_index=True)
        else:
            st.info("Nessuna transazione recente da mostrare")
    else:
        st.info("📭 Nessuna transazione recente trovata")


def transactions_tab(db: DatabaseManager, view: str, start: date | None, end: date | None):
    df = load_transactions_df(db, view, start, end)
    if df.empty:
        st.info("Nessuna transazione")
        return

    # Manual transaction editing section
    st.subheader("📝 Modifica Transazioni")

    # Select transaction to edit
    df_display = df.sort_values("transaction_date", ascending=False).copy()
    df_display["amount_formatted"] = df_display["amount"].apply(fmt_eur)

    # Create a selection interface
    selected_idx = st.selectbox(
        "Seleziona transazione da modificare:",
        range(len(df_display)),
        format_func=lambda x: f"{df_display.iloc[x]['transaction_date'].strftime('%Y-%m-%d')} - {df_display.iloc[x]['description']} - {df_display.iloc[x]['amount_formatted']}",
    )

    if selected_idx is not None:
        selected_tx = df_display.iloc[selected_idx]

        col1, col2 = st.columns(2)

        with col1:
            st.write("**Transazione selezionata:**")
            st.write(f"Data: {selected_tx['transaction_date'].strftime('%Y-%m-%d')}")
            st.write(f"Descrizione: {selected_tx['description']}")
            st.write(f"Importo: {selected_tx['amount_formatted']}")

        with col2:
            st.write("**Modifica spesa condivisa:**")

            # Extract current metadata
            current_meta = {}
            if pd.notna(selected_tx.get("original_data")):
                try:
                    current_meta = json.loads(selected_tx["original_data"])
                except (json.JSONDecodeError, TypeError):
                    pass

            payer = st.selectbox(
                "Chi ha pagato?",
                ["Matteo", "Paola"],
                index=0 if current_meta.get("payer") == "Matteo" else 1,
                key=f"payer_{selected_idx}",
            )
            beneficiary = st.selectbox(
                "Per chi?",
                ["Matteo", "Paola", "Entrambi"],
                index=["Matteo", "Paola", "Entrambi"].index(
                    current_meta.get("beneficiary", "Matteo")
                ),
                key=f"beneficiary_{selected_idx}",
            )

            split_mode = st.selectbox(
                "Ripartizione",
                ["50/50", "% personalizzata", "€ personalizzato"],
                index=["50/50", "% personalizzata", "€ personalizzato"].index(
                    current_meta.get("split_mode", "50/50")
                ),
                key=f"split_mode_{selected_idx}",
            )

            split_values = None
            if split_mode == "50/50":
                split_values = (50.0, 50.0)
            elif split_mode == "% personalizzata":
                current_split = current_meta.get("split_values", [50.0, 50.0])
                p_m = st.number_input(
                    "% Matteo",
                    min_value=0.0,
                    max_value=100.0,
                    value=current_split[0] if current_split else 50.0,
                    step=1.0,
                    key=f"pct_m_{selected_idx}",
                )
                p_p = 100.0 - p_m
                st.caption(f"% Paola: {p_p:.0f}%")
                split_values = (p_m, p_p)
            else:
                current_split = current_meta.get("split_values", [0.0, 0.0])
                e_m = st.number_input(
                    "Quota € Matteo",
                    value=current_split[0] if current_split else 0.0,
                    step=1.0,
                    key=f"eur_m_{selected_idx}",
                )
                e_p = st.number_input(
                    "Quota € Paola",
                    value=current_split[1] if current_split else 0.0,
                    step=1.0,
                    key=f"eur_p_{selected_idx}",
                )
                split_values = (e_m, e_p)

            if st.button("💾 Salva modifiche", key=f"save_{selected_idx}"):
                # Update metadata
                updated_meta = current_meta.copy()
                updated_meta.update(
                    {
                        "payer": payer,
                        "beneficiary": beneficiary,
                        "split_mode": split_mode,
                        "split_values": split_values,
                    }
                )

                # Update in database
                tx_id = selected_tx["id"]
                db.update_transaction_metadata(
                    tx_id, original_data=json.dumps(updated_meta, ensure_ascii=False)
                )
                st.success("✅ Transazione aggiornata!")
                st.rerun()

    st.divider()

    # Display all transactions
    st.subheader("📊 Tutte le Transazioni")
    cols = [
        "transaction_date",
        "user_name",
        "description",
        "amount_formatted",
        "category_name",
        "account",
        "currency",
        "detail",
        "category_hint",
    ]
    show_cols = [c for c in cols if c in df_display.columns]
    st.dataframe(df_display[show_cols], use_container_width=True)


def settings_tab(db: DatabaseManager):
    # Prominent data loading section
    st.header("📥 Carica Dati")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("Importa da provider")
        provider_name = st.selectbox("Provider", list(PROVIDERS.keys()))
        f = st.file_uploader("Seleziona file (CSV/XLSX)", type=["csv", "xlsx"])
        owner = st.selectbox("Utente", ["Matteo", "Paola"], key="import_owner")

        # Default: transactions belong to the user who uploaded them
        st.info(
            "ℹ️ Le transazioni saranno intestate all'utente selezionato. Puoi modificare la ripartizione dopo l'import nel tab Transazioni."
        )

        if f:
            preview = list(PROVIDERS[provider_name].parse(f))
            # enrich preview with bank and category suggestion
            for t in preview:
                t["bank"] = getattr(PROVIDERS[provider_name], "bank_label", provider_name)
                t["category_suggested"] = categorize_row(
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
            user_id = db.get_user_by_name(owner)["id"]
            inserted = 0
            for t in provider.parse(f):
                # bank and category
                t_bank = getattr(provider, "bank_label", provider_name)
                cat = categorize_row(
                    t.get("description", ""), t.get("detail"), t.get("category_hint")
                )
                created, tx_id = db.upsert_transaction_if_new(
                    user_id,
                    t["transaction_date"],
                    t["amount"],
                    t["description"],
                )
                if created:
                    inserted += 1
                if tx_id:
                    meta = {
                        "source": provider_name,
                        "bank": t_bank,
                        "detail": t.get("detail", ""),
                        "category_hint": t.get("category_hint", ""),
                        "category_suggested": cat,
                        "original": t.get("original", {}),
                        "amount_raw": t.get("amount_raw"),
                        "account": t.get("account"),
                        "currency": t.get("currency"),
                        "payer": owner,  # Default to uploader
                        "beneficiary": owner,  # Default to uploader
                        "split_mode": "50/50",
                        "split_values": (50.0, 50.0),
                    }
                    db.update_transaction_metadata(
                        tx_id,
                        import_source=provider_name,
                        original_data=json.dumps(meta, ensure_ascii=False),
                        payee=t["description"],
                        notes=meta["detail"] or None,
                    )
                    # If we want to assign category immediately when confident
                    if cat:
                        existing = db.get_category_by_name(cat)
                        if existing:
                            db.update_transaction_classification(tx_id, category_id=existing["id"])
            st.success(f"✅ Import completato: {inserted} nuove transazioni.")
            st.rerun()

    with col2:
        st.subheader("⚙️ Gestione Database")

        # Database reset with safety popup
        if st.button("🗑️ Reset Database", type="secondary"):
            st.session_state["show_reset_confirm"] = True

        if st.session_state.get("show_reset_confirm", False):
            st.warning("⚠️ **ATTENZIONE: Questa operazione cancellerà TUTTI i dati!**")
            st.write("Digita 'CONFERMA' per procedere:")
            confirm_text = st.text_input("Conferma reset:", key="reset_confirm")

            col_yes, col_no = st.columns(2)
            with col_yes:
                if st.button("✅ Sì, cancella tutto", type="primary"):
                    if confirm_text == "CONFERMA":
                        # Reset database
                        db.reset_database()
                        st.success("🗑️ Database resettato con successo!")
                        st.session_state["show_reset_confirm"] = False
                        st.rerun()
                    else:
                        st.error("Testo di conferma non corretto")
            with col_no:
                if st.button("❌ Annulla"):
                    st.session_state["show_reset_confirm"] = False
                    st.rerun()

        # Database stats
        st.subheader("📊 Statistiche")
        total_tx = len(db.get_transactions(limit=10000))
        total_users = len(db.get_all_users())
        st.metric("Transazioni totali", total_tx)
        st.metric("Utenti", total_users)

        # Quick actions
        st.subheader("🔧 Azioni Rapide")
        if st.button("🔄 Ricarica categorie"):
            db.setup_default_categories()
            st.success("✅ Categorie ricaricate!")

        if st.button("👥 Ricrea utenti"):
            ensure_users(db)
            st.success("✅ Utenti ricreati!")


def main():
    st.set_page_config(
        page_title="Doubloon", page_icon="💰", layout="wide", initial_sidebar_state="expanded"
    )

    # Custom CSS for better styling
    st.markdown(
        """
    <style>
    .main-header {
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 2px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 50px;
        padding-left: 20px;
        padding-right: 20px;
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="main-header"><h1>💰 Doubloon - Expense Tracker di Coppia</h1></div>',
        unsafe_allow_html=True,
    )

    user = login()
    if not user:
        st.info("Effettua il login per continuare")
        return
    db = DatabaseManager()
    ensure_users(db)
    db.setup_default_categories()
    view = user_toggle()

    # Enhanced sidebar with better organization
    st.sidebar.markdown("---")
    st.sidebar.subheader("📅 Filtri Temporali")
    today = pd.Timestamp.today().date()
    default_start = date(today.year, today.month, 1)

    # Quick date presets
    col1, col2 = st.sidebar.columns(2)
    with col1:
        if st.button("📅 Questo mese"):
            st.session_state["start_date"] = default_start
            st.session_state["end_date"] = today
    with col2:
        if st.button("📅 Ultimi 30 giorni"):
            st.session_state["start_date"] = (
                date(today.year, today.month - 1, today.day)
                if today.month > 1
                else date(today.year - 1, 12, today.day)
            )
            st.session_state["end_date"] = today

    start = st.sidebar.date_input(
        "📅 Da", value=st.session_state.get("start_date", default_start), key="start_date_picker"
    )
    end = st.sidebar.date_input(
        "📅 A", value=st.session_state.get("end_date", today), key="end_date_picker"
    )

    # Update session state
    st.session_state["start_date"] = start
    st.session_state["end_date"] = end

    tab_overview, tab_tx, tab_settings = st.tabs(
        ["📊 Overview", "📝 Transazioni", "⚙️ Impostazioni"]
    )
    with tab_overview:
        overview_tab(db, view, start, end)
    with tab_tx:
        transactions_tab(db, view, start, end)
    with tab_settings:
        settings_tab(db)


if __name__ == "__main__":
    main()
