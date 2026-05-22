"""Planning tab — Mutuo | FIRE | Risparmio | Patrimonio | Scenari."""

from datetime import date

import pandas as pd
import streamlit as st

from dashboard.components.charts import amortization_chart, line_trend, monte_carlo_fan
from dashboard.components.kpi_cards import fmt_eur, kpi_row
from planning import (
    FireCalculator,
    MortgageSimulator,
    NetWorthProjector,
    PlanningEngine,
    ScenarioRunner,
    SimulationInputs,
)


def render(db, user_id: int) -> None:
    engine = PlanningEngine(db=db)
    try:
        default_inputs = engine.get_inputs_from_history(user_id)
    except Exception:
        default_inputs = SimulationInputs(
            monthly_net_income=3000,
            monthly_expenses=2000,
            current_savings=10000,
            current_investments_value=0,
            monthly_investment_contribution=500,
        )

    tab_mort, tab_fire, tab_sav, tab_nw, tab_scen = st.tabs(
        ["🏠 Mutuo", "🔥 FIRE", "💰 Risparmio", "🏦 Patrimonio", "🔭 Scenari"]
    )

    with tab_mort:
        _mortgage(db, user_id, default_inputs)
    with tab_fire:
        _fire(default_inputs)
    with tab_sav:
        _savings(default_inputs)
    with tab_nw:
        _net_worth(db, user_id, default_inputs)
    with tab_scen:
        _scenarios(default_inputs)


def _mortgage(db, user_id, defaults):
    st.markdown("#### Simulazione Mutuo")
    col1, col2 = st.columns(2)
    with col1:
        property_price = st.number_input("Prezzo Immobile (€)", value=400_000, step=5_000)
        down_pct = st.slider("Acconto (%)", 10, 50, 20)
        annual_rate = st.number_input("Tasso Annuo (%)", value=3.5, step=0.1, min_value=0.5, max_value=15.0)
        duration = st.selectbox("Durata (anni)", [10, 15, 20, 25, 30], index=3)
    with col2:
        income = st.number_input("Reddito Netto Mensile (€)", value=int(defaults.monthly_net_income), step=100)
        current_savings = st.number_input("Risparmio Attuale (€)", value=int(defaults.current_savings), step=1_000)
        monthly_savings_rate = st.number_input("Risparmio Mensile (€)", value=int(defaults.monthly_savings), step=100)

    sim = MortgageSimulator()
    result = sim.simulate(
        property_price=property_price,
        down_payment_pct=down_pct,
        annual_rate=annual_rate,
        duration_years=duration,
        monthly_net_income=income,
        current_savings=current_savings,
        monthly_savings_rate=monthly_savings_rate,
    )

    afford_color = "#00c851" if result.can_afford else "#ff4444"
    afford_label = "✅ Sostenibile" if result.can_afford else "⚠️ Troppo Costoso"
    kpi_row([
        {"label": "Rata Mensile", "value": fmt_eur(result.monthly_payment), "icon": "📅",
         "variant": "income" if result.can_afford else "expense"},
        {"label": "Interessi Totali", "value": fmt_eur(result.total_interest), "icon": "💸", "variant": "neutral"},
        {"label": "Costo Totale", "value": fmt_eur(result.total_cost), "icon": "🏦", "variant": "neutral"},
        {"label": "LTV", "value": f"{result.ltv_pct:.1f}%", "icon": "📊", "variant": "neutral"},
    ])

    st.markdown(
        f"<div style='padding:0.5rem 1rem;border-radius:8px;background:#1e2130;border:1px solid {afford_color};"
        f"color:{afford_color};font-weight:600;margin-bottom:1rem;display:inline-block;'>{afford_label} "
        f"(rata = {result.monthly_payment/income*100:.1f}% del reddito)</div>",
        unsafe_allow_html=True,
    )

    if result.months_to_down_payment:
        st.info(f"📅 Mesi per accumulare l'acconto: **{result.months_to_down_payment}** ({result.months_to_down_payment//12}a {result.months_to_down_payment%12}m)")

    with st.expander("📊 Piano di Ammortamento"):
        st.plotly_chart(amortization_chart(result.amortization), use_container_width=True)
        st.dataframe(result.amortization.head(60), use_container_width=True, hide_index=True)


def _fire(defaults):
    st.markdown("#### Simulazione FIRE")
    col1, col2 = st.columns(2)
    with col1:
        portfolio = st.number_input("Portafoglio Attuale (€)", value=int(defaults.current_investments_value), step=1000)
        monthly_contrib = st.number_input("Contributo Mensile (€)", value=int(defaults.monthly_investment_contribution), step=100)
        annual_expenses = st.number_input("Spese Annue Previste (€)", value=int(defaults.monthly_expenses * 12), step=500)
    with col2:
        annual_return = st.slider("Rendimento Annuo (%)", 3.0, 12.0, 7.0, 0.5) / 100
        swr = st.slider("Safe Withdrawal Rate (%)", 2.5, 5.0, 4.0, 0.25) / 100
        fire_multiple = 1 / swr

    calc = FireCalculator()
    result = calc.compute(
        current_portfolio=portfolio,
        monthly_contribution=monthly_contrib,
        annual_return=annual_return,
        safe_withdrawal_rate=swr,
        annual_expenses=annual_expenses,
        fire_multiple=fire_multiple,
    )

    kpi_row([
        {"label": "Numero FIRE", "value": fmt_eur(result.fire_number), "icon": "🔥", "variant": "invest"},
        {"label": "Anni al FIRE", "value": str(result.years_to_fire) if result.years_to_fire else ">60", "icon": "⏱️",
         "variant": "income" if (result.years_to_fire or 99) < 30 else "warn"},
        {"label": "Contributo Necessario", "value": fmt_eur(result.monthly_contribution_needed) + "/mo",
         "icon": "💰", "variant": "neutral"},
        {"label": "SWR", "value": f"{swr*100:.2f}%", "icon": "📊", "variant": "neutral"},
    ])

    st.plotly_chart(
        line_trend(result.timeline, "year", ["portfolio_value", "fire_target"], "Traiettoria verso il FIRE"),
        use_container_width=True,
    )


def _savings(defaults):
    st.markdown("#### Proiezione Risparmio con Monte Carlo")
    col1, col2 = st.columns(2)
    with col1:
        current = st.number_input("Risparmio/Investimenti Attuali (€)", value=int(defaults.current_investments_value + defaults.current_savings), step=1000)
        monthly = st.number_input("Contributo Mensile (€)", value=int(defaults.monthly_investment_contribution), step=100)
    with col2:
        years = st.slider("Orizzonte (anni)", 5, 40, 20)
        annual_return = st.slider("Rendimento Annuo (%)", 3.0, 12.0, 7.0, 0.5) / 100
        inflation = st.slider("Inflazione (%)", 1.0, 5.0, 2.5, 0.25) / 100

    inputs = SimulationInputs(
        monthly_net_income=defaults.monthly_net_income,
        monthly_expenses=defaults.monthly_expenses,
        current_savings=defaults.current_savings,
        current_investments_value=current,
        monthly_investment_contribution=monthly,
        investment_annual_return=annual_return,
        inflation_rate=inflation,
        simulation_years=years,
    )
    runner = ScenarioRunner()
    mc = runner.run_monte_carlo(inputs, n_simulations=1000)
    determ = runner.run_deterministic(inputs)

    final_p50 = mc.iloc[-1]["p50"]
    final_p10 = mc.iloc[-1]["p10"]
    final_p90 = mc.iloc[-1]["p90"]

    kpi_row([
        {"label": f"Valore tra {years} anni (p50)", "value": fmt_eur(final_p50), "icon": "📊", "variant": "invest"},
        {"label": "Scenario pessimista (p10)", "value": fmt_eur(final_p10), "icon": "⬇️", "variant": "neutral"},
        {"label": "Scenario ottimista (p90)", "value": fmt_eur(final_p90), "icon": "⬆️", "variant": "income"},
    ])

    st.plotly_chart(monte_carlo_fan(mc, f"Fan Chart Monte Carlo ({years} anni, n=1000)"), use_container_width=True)


def _net_worth(db, user_id, defaults):
    st.markdown("#### Aggiungi Snapshot Patrimonio")
    today = date.today()
    col1, col2 = st.columns(2)
    with col1:
        snap_date = st.date_input("Data", value=today)
        cash = st.number_input("Liquidità (conti correnti) €", value=0.0, step=100.0)
        investments = st.number_input("Investimenti €", value=float(defaults.current_investments_value), step=100.0)
        real_estate = st.number_input("Immobili €", value=0.0, step=1000.0)
    with col2:
        other_assets = st.number_input("Altri asset €", value=0.0, step=100.0)
        mortgage_debt = st.number_input("Debito mutuo €", value=0.0, step=1000.0)
        other_debts = st.number_input("Altri debiti €", value=0.0, step=100.0)
        notes = st.text_input("Note", value="")

    net = cash + investments + real_estate + other_assets - mortgage_debt - other_debts
    st.metric("Patrimonio Netto Calcolato", fmt_eur(net))

    if st.button("💾 Salva Snapshot", type="primary"):
        db.upsert_networth_snapshot(user_id, {
            "snapshot_date": str(snap_date),
            "cash_amount": cash,
            "investments_amount": investments,
            "real_estate_amount": real_estate,
            "other_assets_amount": other_assets,
            "mortgage_debt": mortgage_debt,
            "other_debts": other_debts,
            "notes": notes or None,
        })
        st.success("✅ Snapshot salvato!")
        st.rerun()

    # Historical chart
    snaps = db.get_networth_snapshots(user_id, limit=200)
    if len(snaps) >= 2:
        st.divider()
        st.markdown("#### Storico")
        df = pd.DataFrame(snaps)[["snapshot_date", "net_worth", "cash_amount", "investments_amount"]].sort_values("snapshot_date")
        df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
        st.plotly_chart(line_trend(df, "snapshot_date", ["net_worth", "investments_amount"], "Patrimonio Netto nel Tempo"),
                        use_container_width=True)


def _scenarios(defaults):
    st.markdown("#### Confronto Scenari Stipendio")
    col1, col2 = st.columns(2)
    with col1:
        years = st.slider("Orizzonte (anni)", 5, 40, 20, key="scen_years")
        r0 = st.number_input("Scenario 1: crescita stipendio %", value=0.0, step=0.5)
        r1 = st.number_input("Scenario 2: crescita stipendio %", value=3.0, step=0.5)
    with col2:
        r2 = st.number_input("Scenario 3: crescita stipendio %", value=5.0, step=0.5)
        r3 = st.number_input("Scenario 4: crescita stipendio %", value=8.0, step=0.5)

    inputs = SimulationInputs(
        monthly_net_income=defaults.monthly_net_income,
        monthly_expenses=defaults.monthly_expenses,
        current_savings=defaults.current_savings,
        current_investments_value=defaults.current_investments_value,
        monthly_investment_contribution=defaults.monthly_investment_contribution,
        simulation_years=years,
    )
    runner = ScenarioRunner()
    scenarios = runner.run_salary_scenarios(inputs, salary_growth_rates=[r/100 for r in [r0, r1, r2, r3]])

    # Combined deterministic chart
    import plotly.graph_objects as go
    from dashboard.components.theme import PLOTLY_TEMPLATE, PALETTE
    fig = go.Figure()
    colors = [PALETTE["primary"], PALETTE["income"], PALETTE["investment"], PALETTE["neutral"]]
    for s, color in zip(scenarios, colors):
        fig.add_trace(go.Scatter(x=s.deterministic["year"], y=s.deterministic["net_worth"],
                                 name=s.label, line=dict(color=color, width=2)))
    fig.update_layout(title="Confronto Scenari — Patrimonio Netto",
                      xaxis_title="Anno", yaxis_title="€", **PLOTLY_TEMPLATE["layout"])
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("#### Risultati a " + str(years) + " anni")
    rows = [{"Scenario": s.label, "Patrimonio Netto": fmt_eur(s.deterministic.iloc[-1]["net_worth"]),
             "Reddito Mensile": fmt_eur(s.deterministic.iloc[-1]["monthly_income"])} for s in scenarios]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
