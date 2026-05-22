"""Expenses tab — Personali | Lavoro | Budget sub-tabs."""

import pandas as pd
import plotly.express as px
import streamlit as st

from dashboard.components.charts import bar_monthly, pie_allocation
from dashboard.components.kpi_cards import fmt_eur, kpi_row
from dashboard.components.theme import PALETTE, badge


def render(db, tx_svc, filters, user_id: int, cat_svc) -> None:
    st_pers, st_lav, st_bud = st.tabs(["👤 Personali", "💼 Lavoro", "🎯 Budget"])

    with st_pers:
        _render_personal(db, tx_svc, filters, cat_svc)
    with st_lav:
        _render_work(db, user_id)
    with st_bud:
        _render_budget(db, tx_svc, filters, user_id)


# ------------------------------------------------------------------
# Personali
# ------------------------------------------------------------------

def _render_personal(db, tx_svc, filters, cat_svc) -> None:
    df = tx_svc.get_transactions_df(filters)
    if df.empty:
        st.info("📭 Nessuna transazione per il periodo selezionato")
        return

    col1, col2, col3 = st.columns(3)
    categories = sorted(df["category_name"].dropna().unique().tolist()) if "category_name" in df.columns else []
    with col1:
        selected_cats = st.multiselect("Categorie", categories, placeholder="Tutte")
    with col2:
        search = st.text_input("Cerca", placeholder="Parola chiave…")
    with col3:
        tx_type_filter = st.selectbox("Tipo", ["Tutti", "Uscite", "Entrate"])

    _df = df.copy()
    if selected_cats:
        _df = _df[_df["category_name"].isin(selected_cats)]
    if search:
        mask = _df["description"].str.contains(search, case=False, na=False)
        if "detail" in _df.columns:
            mask |= _df["detail"].str.contains(search, case=False, na=False)
        _df = _df[mask]
    if tx_type_filter == "Uscite":
        _df = _df[_df["amount"] < 0]
    elif tx_type_filter == "Entrate":
        _df = _df[_df["amount"] > 0]

    total_spent = _df[_df["amount"] < 0]["amount"].sum()
    total_income = _df[_df["amount"] > 0]["amount"].sum()
    net = _df["amount"].sum()

    kpi_row([
        {"label": "Spesa Totale", "value": fmt_eur(total_spent), "icon": "💸", "variant": "expense"},
        {"label": "Entrate Totali", "value": fmt_eur(total_income), "icon": "💰", "variant": "income"},
        {"label": "Saldo Netto", "value": fmt_eur(net), "icon": "📊", "variant": "income" if net >= 0 else "expense"},
        {"label": "Transazioni", "value": f"{len(_df):,}", "icon": "🗓️", "variant": "neutral"},
    ])

    c1, c2 = st.columns(2)
    with c1:
        _df["month"] = _df["transaction_date"].dt.to_period("M").dt.to_timestamp()
        trend = _df.groupby(["month", "category_name"], dropna=False)["amount"].sum().reset_index()
        if not trend.empty:
            st.plotly_chart(bar_monthly(trend, "month", "amount", "category_name", "Trend Mensile per Categoria"),
                            use_container_width=True)
    with c2:
        expense_df = _df[_df["amount"] < 0]
        alloc = expense_df.groupby("category_name", dropna=False)["amount"].sum().abs().reset_index()
        if not alloc.empty:
            st.plotly_chart(pie_allocation(alloc, "category_name", "amount", "Distribuzione Spese"),
                            use_container_width=True)

    st.markdown("#### Transazioni")
    disp = _df.sort_values("transaction_date", ascending=False).copy()
    disp["Importo"] = disp["amount"].apply(fmt_eur)
    disp["Data"] = disp["transaction_date"].dt.strftime("%d/%m/%Y")
    show_cols = [c for c in ["Data", "description", "Importo", "category_name", "account"] if c in disp.columns]
    st.dataframe(disp[show_cols].rename(columns={"description": "Descrizione", "category_name": "Categoria", "account": "Conto"}),
                 use_container_width=True, hide_index=True)

    _edit_category_section(db, tx_svc, _df, cat_svc)


def _edit_category_section(db, tx_svc, df, cat_svc) -> None:
    with st.expander("✏️ Modifica Categoria"):
        if df.empty:
            return
        df_sorted = df.sort_values("transaction_date", ascending=False).copy()
        df_sorted["_label"] = df_sorted.apply(
            lambda r: f"{r['transaction_date'].strftime('%d/%m/%Y')} — {r['description'][:40]} — {fmt_eur(r['amount'])}", axis=1
        )
        idx = st.selectbox("Transazione", range(len(df_sorted)), format_func=lambda x: df_sorted.iloc[x]["_label"])
        if idx is not None:
            tx = df_sorted.iloc[idx]
            current = tx.get("category_name")
            new_cat = st.selectbox("Categoria", [None] + cat_svc.ALL,
                                   index=([None] + cat_svc.ALL).index(current) if current in cat_svc.ALL else 0,
                                   format_func=lambda x: x or "— nessuna —")
            if st.button("💾 Salva"):
                if new_cat:
                    existing = db.get_category_by_name(new_cat)
                    if existing:
                        tx_svc.update_classification(int(tx["id"]), category_id=existing["id"])
                        st.success("✅ Categoria aggiornata!")
                        st.rerun()


# ------------------------------------------------------------------
# Lavoro / Rimborsi
# ------------------------------------------------------------------

def _render_work(db, user_id: int) -> None:
    summary = db.get_reimbursement_summary(user_id)
    pending_total = summary.get("pending_total") or 0.0
    submitted_total = summary.get("submitted_total") or 0.0
    reimbursed_ytd = summary.get("reimbursed_ytd") or 0.0
    pending_count = summary.get("pending_count") or 0
    submitted_count = summary.get("submitted_count") or 0

    kpi_row([
        {"label": f"In Attesa ({pending_count})", "value": fmt_eur(pending_total), "icon": "⏳", "variant": "warn"},
        {"label": f"Inviate ({submitted_count})", "value": fmt_eur(submitted_total), "icon": "📤", "variant": "invest"},
        {"label": "Rimborsate YTD", "value": fmt_eur(reimbursed_ytd), "icon": "✅", "variant": "income"},
    ])

    # Kanban columns
    c_pend, c_sub, c_reimb = st.columns(3)
    statuses = [("pending", c_pend, "⏳ In Attesa"), ("submitted", c_sub, "📤 Inviate"), ("reimbursed", c_reimb, "✅ Rimborsate")]

    for status, col, title in statuses:
        with col:
            st.markdown(f"**{title}**")
            expenses = db.get_work_expenses(user_id=user_id, status=status)
            if not expenses:
                st.caption("Nessuna spesa")
            for exp in expenses[:15]:
                amount_str = fmt_eur(abs(exp["amount"]))
                st.markdown(
                    f"""<div style="background:#1e2130;border:1px solid #2d3555;border-radius:10px;padding:0.7rem;margin-bottom:0.5rem;">
                    <div style="font-size:0.85rem;color:#e0e0e0;font-weight:600;">{exp['description'][:35]}</div>
                    <div style="font-size:0.78rem;color:#8892a4;">{exp['transaction_date']}</div>
                    <div style="font-size:1rem;font-weight:700;color:{PALETTE['expense']};margin-top:0.2rem;">{amount_str}</div>
                    </div>""",
                    unsafe_allow_html=True,
                )

    st.divider()

    # Mark expense as work expense
    col_mark, col_link = st.columns(2)
    with col_mark:
        st.markdown("#### Segna come Spesa Lavoro")
        from services.transactions import TransactionFilters
        from datetime import date
        start_3m = (pd.Timestamp.today() - pd.DateOffset(months=3)).date()
        recent_tx = db.get_transactions(user_id=user_id, start_date=str(start_3m), end_date=str(date.today()), limit=200)
        non_work = [t for t in recent_tx if not t.get("is_work_expense") and t["amount"] < 0]
        if non_work:
            tx_labels = [f"{t['transaction_date']} — {t['description'][:35]} — {fmt_eur(abs(t['amount']))}" for t in non_work]
            sel = st.selectbox("Transazione", range(len(non_work)), format_func=lambda x: tx_labels[x])
            new_status = st.selectbox("Stato", ["pending", "submitted"])
            if st.button("📌 Segna come Spesa Lavoro"):
                db.mark_work_expense(non_work[sel]["id"], status=new_status)
                st.success("✅ Spesa segnata!")
                st.rerun()

    with col_link:
        st.markdown("#### Collega Rimborso Aggregato")
        unlinked = db.get_unlinked_reimbursements(user_id)
        if unlinked:
            reimb_labels = [f"{r['transaction_date']} — {r['description'][:30]} — {fmt_eur(r['amount'])}" for r in unlinked]
            sel_reimb = st.selectbox("Bonifico rimborso", range(len(unlinked)), format_func=lambda x: reimb_labels[x])
            pending_exp = db.get_work_expenses(user_id=user_id, status="submitted")
            if pending_exp:
                exp_labels = [f"{e['transaction_date']} — {e['description'][:30]} — {fmt_eur(abs(e['amount']))}" for e in pending_exp]
                sel_exps = st.multiselect("Spese collegate", range(len(pending_exp)), format_func=lambda x: exp_labels[x])
                if sel_exps and st.button("🔗 Collega", type="primary"):
                    total_expense = sum(abs(pending_exp[i]["amount"]) for i in sel_exps)
                    for i in sel_exps:
                        allocated = abs(pending_exp[i]["amount"])
                        db.link_reimbursement(
                            unlinked[sel_reimb]["id"],
                            pending_exp[i]["id"],
                            allocated,
                        )
                    st.success(f"✅ Collegate {len(sel_exps)} spese → rimborso {fmt_eur(total_expense)}")
                    st.rerun()
        else:
            st.caption("Nessun bonifico di rimborso senza collegamento trovato")


# ------------------------------------------------------------------
# Budget
# ------------------------------------------------------------------

def _render_budget(db, tx_svc, filters, user_id: int) -> None:
    df = tx_svc.get_transactions_df(filters)
    today = pd.Timestamp.today()

    # Show budget vs actual per category
    expenses = df[df["amount"] < 0].copy() if not df.empty else pd.DataFrame()
    by_cat = expenses.groupby("category_name", dropna=False)["amount"].sum().abs().reset_index() if not expenses.empty else pd.DataFrame()

    st.markdown("#### Speso vs Budget")
    if by_cat.empty:
        st.info("Nessuna spesa nel periodo selezionato")
    else:
        with db.get_connection() as conn:
            budgets = conn.execute(
                """SELECT c.name, bt.target_amount
                   FROM budget_targets bt
                   JOIN categories c ON bt.category_id = c.id
                   WHERE bt.user_id=? AND bt.period_year=? AND (bt.period_month IS NULL OR bt.period_month=?)""",
                (user_id, today.year, today.month),
            ).fetchall()
        budget_map = {r[0]: float(r[1]) for r in budgets}

        for _, row in by_cat.iterrows():
            cat = row["category_name"] or "Senza categoria"
            spent = float(row["amount"])
            budget = budget_map.get(cat)
            col1, col2 = st.columns([3, 1])
            with col1:
                if budget:
                    pct = min(spent / budget, 1.0)
                    color = "#ff4444" if pct >= 0.9 else ("#ffd700" if pct >= 0.7 else "#667eea")
                    st.markdown(f"**{cat}**")
                    st.progress(pct)
                    st.caption(f"{fmt_eur(spent)} / {fmt_eur(budget)}")
                else:
                    st.markdown(f"**{cat}** — {fmt_eur(spent)} _(nessun budget impostato)_")
            with col2:
                if budget:
                    remaining = budget - spent
                    lbl = "Rimasto" if remaining >= 0 else "Sforato"
                    st.metric(lbl, fmt_eur(abs(remaining)))

    st.divider()
    st.markdown("#### Imposta Budget")
    cats = db.get_all_users()  # get categories
    with db.get_connection() as conn:
        all_cats = conn.execute("SELECT id, name FROM categories ORDER BY name").fetchall()

    if all_cats:
        cat_name = st.selectbox("Categoria", [r[1] for r in all_cats])
        cat_id = next(r[0] for r in all_cats if r[1] == cat_name)
        budget_amount = st.number_input("Budget mensile (€)", min_value=0.0, step=10.0)
        if st.button("💾 Salva Budget"):
            with db.get_connection() as conn:
                conn.execute(
                    """INSERT INTO budget_targets (user_id, category_id, period_year, period_month, target_amount)
                       VALUES (?,?,?,?,?)
                       ON CONFLICT(user_id,category_id,period_year,period_month)
                       DO UPDATE SET target_amount=excluded.target_amount, updated_at=CURRENT_TIMESTAMP""",
                    (user_id, cat_id, today.year, today.month, budget_amount),
                )
                conn.commit()
            st.success(f"✅ Budget {cat_name}: {fmt_eur(budget_amount)}/mese")
            st.rerun()
