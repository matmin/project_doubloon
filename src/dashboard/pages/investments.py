"""Investments tab — Portafoglio | P&L | Allocazione | Performance | Storico."""

import pandas as pd
import streamlit as st

from dashboard.components.charts import (
    benchmark_line,
    line_trend,
    pie_allocation,
    pnl_bar,
)
from dashboard.components.kpi_cards import fmt_eur, kpi_row
from investments import BenchmarkService, ISINMapper, PnLCalculator, PortfolioService, PriceFetcher


def render(db, user_id: int) -> None:
    mapper = ISINMapper(db=db)
    fetcher = PriceFetcher(db=db, isin_mapper=mapper)
    ps = PortfolioService(db=db)
    pnl = PnLCalculator(db=db)
    bench = BenchmarkService(db=db)

    tab_port, tab_pnl, tab_alloc, tab_perf, tab_hist = st.tabs(
        ["📊 Portafoglio", "💹 P&L", "🥧 Allocazione", "📈 Performance", "📋 Storico"]
    )

    with tab_port:
        _portfolio(db, ps, fetcher, user_id)
    with tab_pnl:
        _pnl_tab(pnl, user_id)
    with tab_alloc:
        _allocation(ps, user_id)
    with tab_perf:
        _performance(bench, user_id)
    with tab_hist:
        _history(db, user_id)


def _portfolio(db, ps, fetcher, user_id):
    col_refresh, _ = st.columns([1, 4])
    with col_refresh:
        if st.button("🔄 Aggiorna Prezzi"):
            updated = fetcher.refresh_all_positions(user_id)
            st.success(f"Aggiornati {updated} titoli")
            st.rerun()

    positions = ps.get_positions(user_id)
    active = [p for p in positions if p.get("is_active")]

    if not active:
        st.info("Nessuna posizione attiva. Importa transazioni da Trade Republic, Scalable o Revolut Invest.")
        return

    total_cost = sum(float(p.get("total_cost_basis") or 0) for p in active)
    total_value = sum(
        float(p.get("shares", 0)) * float(p.get("current_price") or p.get("avg_cost_per_share") or 0)
        for p in active
    )
    total_unr = total_value - total_cost if total_cost else 0.0
    total_unr_pct = (total_unr / total_cost * 100) if total_cost else 0.0

    kpi_row([
        {"label": "Investito Totale", "value": fmt_eur(total_cost), "icon": "💵", "variant": "neutral"},
        {"label": "Valore Attuale", "value": fmt_eur(total_value), "icon": "💰", "variant": "invest"},
        {"label": "P&L Non Realizzato",
         "value": fmt_eur(total_unr),
         "variant": "income" if total_unr >= 0 else "expense",
         "delta": f"{total_unr_pct:+.2f}%",
         "delta_positive": total_unr >= 0},
        {"label": "Posizioni Attive", "value": str(len(active)), "icon": "📑", "variant": "neutral"},
    ])

    rows = []
    for p in active:
        shares = float(p.get("shares", 0))
        avg_cost = float(p.get("avg_cost_per_share") or 0)
        cur_price = float(p.get("current_price") or 0)
        cost_basis = shares * avg_cost
        cur_value = shares * cur_price if cur_price else None
        unr = cur_value - cost_basis if cur_value is not None else None
        unr_pct = (unr / cost_basis * 100) if (cost_basis and unr is not None) else None
        rows.append({
            "Titolo": p.get("asset_name", p.get("isin", "?")),
            "ISIN": p.get("isin", ""),
            "Broker": p.get("broker", ""),
            "Tipo": p.get("asset_type") or "",
            "Azioni": f"{shares:.4f}",
            "Costo Medio": fmt_eur(avg_cost),
            "Prezzo Live": fmt_eur(cur_price) if cur_price else "—",
            "Costo Totale": fmt_eur(cost_basis),
            "Valore": fmt_eur(cur_value) if cur_value is not None else "—",
            "P&L %": f"{unr_pct:+.2f}%" if unr_pct is not None else "—",
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def _pnl_tab(pnl, user_id):
    totals = pnl.compute_total_return(user_id)
    realized_pnl = totals.get("realized_pnl", 0.0) or 0.0
    unrealized_pnl = totals.get("unrealized_pnl")
    total_pnl = totals.get("total_pnl", 0.0) or 0.0
    return_pct = totals.get("return_pct")

    kpi_row([
        {"label": "P&L Realizzato", "value": fmt_eur(realized_pnl), "icon": "✅",
         "variant": "income" if realized_pnl >= 0 else "expense"},
        {"label": "P&L Non Realizzato",
         "value": fmt_eur(unrealized_pnl) if unrealized_pnl is not None else "—", "icon": "📈",
         "variant": "invest"},
        {"label": "P&L Totale", "value": fmt_eur(total_pnl), "icon": "💹",
         "variant": "income" if total_pnl >= 0 else "expense"},
        {"label": "Rendimento", "value": f"{return_pct:+.2f}%" if return_pct is not None else "—",
         "icon": "📊", "variant": "income" if (return_pct or 0) >= 0 else "expense"},
    ])

    st.markdown("#### P&L Realizzato per Trade")
    realized = pnl.compute_realized_pnl(user_id)
    if not realized.empty:
        st.plotly_chart(pnl_bar(realized, "P&L Netto per Vendita"), use_container_width=True)
        st.dataframe(
            realized[["transaction_date", "isin", "description", "shares_sold",
                       "avg_cost", "sell_price", "net_pnl"]].rename(columns={
                "transaction_date": "Data", "isin": "ISIN", "description": "Titolo",
                "shares_sold": "Azioni Vendute", "avg_cost": "Costo Medio",
                "sell_price": "Prezzo Vendita", "net_pnl": "P&L Netto",
            }),
            use_container_width=True, hide_index=True,
        )
    else:
        st.info("Nessuna vendita registrata")

    st.markdown("#### P&L Non Realizzato per Posizione")
    unrealized = pnl.compute_unrealized_pnl(user_id)
    if not unrealized.empty:
        st.dataframe(
            unrealized[["asset_name", "isin", "shares", "avg_cost", "current_price",
                         "cost_basis", "current_value", "unrealized_pnl", "unrealized_pnl_pct"]].rename(columns={
                "asset_name": "Titolo", "isin": "ISIN", "shares": "Azioni",
                "avg_cost": "Costo Medio", "current_price": "Prezzo Attuale",
                "cost_basis": "Costo Totale", "current_value": "Valore",
                "unrealized_pnl": "P&L", "unrealized_pnl_pct": "P&L %",
            }),
            use_container_width=True, hide_index=True,
        )


def _allocation(ps, user_id):
    c1, c2 = st.columns(2)
    with c1:
        by_class = ps.get_allocation_by_asset_class(user_id)
        if not by_class.empty:
            st.plotly_chart(pie_allocation(by_class, "asset_type", "value", "Per Classe Asset"),
                            use_container_width=True)
        else:
            st.info("Nessun dato")
    with c2:
        by_broker = ps.get_allocation_by_broker(user_id)
        if not by_broker.empty:
            st.plotly_chart(pie_allocation(by_broker, "broker", "value", "Per Broker"),
                            use_container_width=True)
        else:
            st.info("Nessun dato")


def _performance(bench, user_id):
    benchmark_label = st.selectbox("Benchmark", bench.available_benchmarks())
    start_years = st.selectbox("Periodo", [1, 2, 3, 5], index=0, format_func=lambda x: f"{x} anno" if x == 1 else f"{x} anni")

    from datetime import date, timedelta
    start = date.today() - timedelta(days=start_years * 365)
    df_cmp = bench.get_portfolio_vs_benchmark(user_id, benchmark_label=benchmark_label, start_date=start)

    if df_cmp is not None:
        st.plotly_chart(benchmark_line(df_cmp), use_container_width=True)
    else:
        st.info("💡 Aggiungi snapshot del patrimonio netto nel tab **Home → Patrimonio** per abilitare il confronto con benchmark.")


def _history(db, user_id):
    txs = db.get_investment_transactions(user_id)
    if not txs:
        st.info("Nessuna transazione di investimento. Importa file CSV da Trade Republic, Scalable, o Revolut Invest.")
        return
    df = pd.DataFrame(txs)
    show_cols = [c for c in ["transaction_date", "description", "isin", "asset_type",
                              "shares", "price_per_share", "amount", "fee", "tax",
                              "source_bank"] if c in df.columns]
    st.dataframe(
        df[show_cols].sort_values("transaction_date", ascending=False).rename(columns={
            "transaction_date": "Data", "description": "Descrizione", "isin": "ISIN",
            "asset_type": "Tipo", "shares": "Azioni", "price_per_share": "Prezzo",
            "amount": "Importo", "fee": "Fee", "tax": "Tasse", "source_bank": "Broker",
        }),
        use_container_width=True, hide_index=True,
    )
