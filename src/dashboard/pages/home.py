"""Home tab — net worth snapshot, cash flow, savings rate."""

import pandas as pd
import streamlit as st

from dashboard.components.charts import bar_monthly, line_trend
from dashboard.components.kpi_cards import fmt_eur, kpi_row


def render(db, tx_svc, user_id: int) -> None:
    st.subheader("🏠 Panoramica Finanziaria")

    # --- Cash flow del mese corrente ---
    today = pd.Timestamp.today()
    start_m = today.replace(day=1).date()
    end_m = today.date()

    from services.transactions import TransactionFilters
    filters_month = TransactionFilters(start_date=start_m, end_date=end_m)
    df_month = tx_svc.get_transactions_df(filters_month)

    income_m = float(df_month[df_month["amount"] > 0]["amount"].sum()) if not df_month.empty else 0.0
    expense_m = float(df_month[df_month["amount"] < 0]["amount"].sum()) if not df_month.empty else 0.0
    net_m = income_m + expense_m
    savings_rate = (net_m / income_m * 100) if income_m > 0 else 0.0

    # Work expense alert
    summary = db.get_reimbursement_summary(user_id)
    pending_count = summary.get("pending_count") or 0
    pending_total = summary.get("pending_total") or 0.0

    # Net worth from latest snapshot
    snaps = db.get_networth_snapshots(user_id, limit=1)
    net_worth = snaps[0]["net_worth"] if snaps else None
    invest_val = snaps[0]["investments_amount"] if snaps else None

    kpi_row([
        {
            "label": "Patrimonio Netto",
            "value": fmt_eur(net_worth) if net_worth is not None else "— aggiungi snapshot",
            "icon": "🏦",
            "variant": "neutral",
        },
        {
            "label": "Entrate Mese",
            "value": fmt_eur(income_m),
            "icon": "💰",
            "variant": "income",
        },
        {
            "label": "Uscite Mese",
            "value": fmt_eur(expense_m),
            "icon": "💸",
            "variant": "expense",
        },
        {
            "label": "Saldo Netto",
            "value": fmt_eur(net_m),
            "icon": "📊",
            "variant": "income" if net_m >= 0 else "expense",
        },
    ])

    # Savings rate gauge
    col1, col2 = st.columns([1, 2])
    with col1:
        st.markdown("#### Tasso di Risparmio")
        color = "#00c851" if savings_rate >= 20 else ("#ffd700" if savings_rate >= 10 else "#ff4444")
        st.markdown(
            f"""<div style="background:#1e2130;border-radius:12px;padding:1rem;text-align:center;border:1px solid #2d3555;">
            <div style="font-size:2.5rem;font-weight:700;color:{color};">{savings_rate:.1f}%</div>
            <div style="color:#8892a4;font-size:0.85rem;margin-top:0.3rem;">questo mese</div>
            </div>""",
            unsafe_allow_html=True,
        )
        if invest_val is not None:
            st.metric("Portafoglio Investimenti", fmt_eur(invest_val))

    with col2:
        # 6-month cash flow trend
        start_6m = (today - pd.DateOffset(months=6)).date()
        filters_6m = TransactionFilters(start_date=start_6m, end_date=today.date())
        df_6m = tx_svc.get_transactions_df(filters_6m)
        if not df_6m.empty:
            df_6m["month"] = df_6m["transaction_date"].dt.to_period("M").dt.to_timestamp()
            monthly = df_6m.groupby("month")["amount"].sum().reset_index()
            monthly.columns = ["month", "amount"]
            if not monthly.empty:
                fig = bar_monthly(monthly, "month", "amount", title="Cash Flow Mensile (6 mesi)")
                st.plotly_chart(fig, use_container_width=True)

    # Alerts
    if pending_count > 0:
        st.warning(
            f"⚠️ **{pending_count} spese lavorative** in attesa di rimborso — totale {fmt_eur(pending_total)}"
        )

    # Net worth history chart
    from investments.benchmarks import BenchmarkService
    projector_snaps = db.get_networth_snapshots(user_id, limit=500)
    if len(projector_snaps) >= 2:
        st.markdown("#### Storico Patrimonio Netto")
        df_snaps = pd.DataFrame(projector_snaps)
        df_snaps = df_snaps[["snapshot_date", "net_worth", "cash_amount", "investments_amount"]].sort_values("snapshot_date")
        df_snaps["snapshot_date"] = pd.to_datetime(df_snaps["snapshot_date"])
        fig_nw = line_trend(
            df_snaps,
            x="snapshot_date",
            y=["net_worth", "investments_amount"],
            title="",
        )
        st.plotly_chart(fig_nw, use_container_width=True)
    else:
        st.info("💡 Aggiungi snapshot nel tab **Patrimonio** per vedere l'andamento nel tempo.")
