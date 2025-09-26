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
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
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
        st.info("Nessuna transazione trovata")
        return
    # Filters row
    categories = (
        sorted([c for c in df["category_name"].dropna().unique()])
        if "category_name" in df.columns
        else []
    )
    col1, col2, col3 = st.columns([2, 2, 2])
    selected_cats = col1.multiselect("Categorie", categories)
    search = col2.text_input("Cerca testo")
    min_amt, max_amt = col3.columns(2)
    min_val = min_amt.number_input("Min €", value=0.0)
    max_val = max_amt.number_input("Max €", value=0.0)
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

    # KPIs
    total_spent = _df[_df["amount"] < 0]["amount"].sum()
    total_income = _df[_df["amount"] > 0]["amount"].sum()
    net = _df["amount"].sum()
    k1, k2, k3 = st.columns(3)
    k1.metric("Spesa", fmt_eur(total_spent))
    k2.metric("Entrate", fmt_eur(total_income))
    k3.metric("Netto", fmt_eur(net))

    _df["month"] = _df["transaction_date"].dt.to_period("M").dt.to_timestamp()
    trend = _df.groupby(["month", "category_name"], dropna=False)["amount"].sum().reset_index()
    st.plotly_chart(
        px.bar(
            trend, x="month", y="amount", color="category_name", title="Trend mensile per categoria"
        ),
        use_container_width=True,
    )
    pie_df = _df[_df["amount"] < 0]
    alloc = pie_df.groupby("category_name", dropna=False)["amount"].sum().abs().reset_index()
    cpie, ctop = st.columns(2)
    if not alloc.empty:
        cpie.plotly_chart(
            px.pie(alloc, names="category_name", values="amount", title="Allocazione spese"),
            use_container_width=True,
        )
        top = alloc.sort_values("amount", ascending=False).head(5)
        ctop.plotly_chart(
            px.bar(top, x="category_name", y="amount", title="Top categorie"),
            use_container_width=True,
        )

    # Recent transactions panel
    st.subheader("Recenti")
    recent = _df.sort_values("transaction_date", ascending=False).head(20).copy()
    if not recent.empty and "amount" in recent.columns:
        recent["amount"] = recent["amount"].apply(fmt_eur)
    cols = ["transaction_date", "user_name", "description", "amount", "category_name", "account"]
    show_cols = [c for c in cols if c in recent.columns]
    st.dataframe(recent[show_cols], use_container_width=True)


def transactions_tab(db: DatabaseManager, view: str, start: date | None, end: date | None):
    df = load_transactions_df(db, view, start, end)
    if df.empty:
        st.info("Nessuna transazione")
        return
    df = df.sort_values("transaction_date", ascending=False).copy()
    df["amount_formatted"] = df["amount"].apply(fmt_eur)
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
    show_cols = [c for c in cols if c in df.columns]
    st.dataframe(df[show_cols], use_container_width=True)


def settings_tab(db: DatabaseManager):
    st.subheader("Importa da provider")
    provider_name = st.selectbox("Provider", list(PROVIDERS.keys()))
    f = st.file_uploader("Seleziona file (CSV/XLSX)", type=["csv", "xlsx"])
    owner = st.selectbox("Utente", ["Matteo", "Paola"], key="import_owner")

    if f:
        preview = list(PROVIDERS[provider_name].parse(f))
        prev_df = pd.DataFrame(preview[:10])
        if not prev_df.empty and "amount" in prev_df.columns:
            prev_df["amount_formatted"] = prev_df["amount"].apply(fmt_eur)
        st.write("Anteprima (prime 10):")
        st.dataframe(prev_df, use_container_width=True)
        f.seek(0)

    if f and st.button("Importa in DB"):
        provider = PROVIDERS[provider_name]
        user_id = db.get_user_by_name(owner)["id"]
        inserted = 0
        for t in provider.parse(f):
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
                    "detail": t.get("detail", ""),
                    "category_hint": t.get("category_hint", ""),
                    "original": t.get("original", {}),
                    "amount_raw": t.get("amount_raw"),
                    "account": t.get("account"),
                    "currency": t.get("currency"),
                }
                db.update_transaction_metadata(
                    tx_id,
                    import_source=provider_name,
                    original_data=json.dumps(meta, ensure_ascii=False),
                    payee=t["description"],
                    notes=meta["detail"] or None,
                )
        st.success(f"Import completato: {inserted} nuove transazioni.")


def main():
    st.set_page_config(page_title="Doubloon", page_icon="💰", layout="wide")
    st.title("💰 Doubloon - Expense Tracker di Coppia")

    user = login()
    if not user:
        st.info("Effettua il login per continuare")
        return
    db = DatabaseManager()
    ensure_users(db)
    db.setup_default_categories()
    view = user_toggle()

    st.sidebar.header("Filtri")
    today = pd.Timestamp.today().date()
    default_start = date(today.year, today.month, 1)
    start = st.sidebar.date_input("Da", value=default_start)
    end = st.sidebar.date_input("A", value=today)

    tab_overview, tab_tx, tab_settings = st.tabs(["Overview", "Transazioni", "Impostazioni"])
    with tab_overview:
        overview_tab(db, view, start, end)
    with tab_tx:
        transactions_tab(db, view, start, end)
    with tab_settings:
        settings_tab(db)


if __name__ == "__main__":
    main()
