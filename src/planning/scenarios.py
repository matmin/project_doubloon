"""Deterministic + Monte Carlo scenario runner."""

from dataclasses import dataclass
from typing import Optional

import numpy as np
import pandas as pd

from .engine import SimulationInputs


@dataclass
class ScenarioResult:
    label: str
    deterministic: pd.DataFrame  # year, net_worth, savings, investments
    monte_carlo: Optional[pd.DataFrame] = None  # year, p10, p25, p50, p75, p90


class ScenarioRunner:

    def run_deterministic(
        self,
        inputs: SimulationInputs,
        label: str = "Base",
    ) -> pd.DataFrame:
        rows = []
        savings = inputs.current_savings
        investments = inputs.current_investments_value
        income = inputs.monthly_net_income
        expenses = inputs.monthly_expenses

        for year in range(1, inputs.simulation_years + 1):
            income_scale = (1 + inputs.annual_salary_growth_rate) ** year
            exp_scale = (1 + inputs.inflation_rate) ** year
            monthly_income = income * income_scale
            monthly_exp = expenses * exp_scale
            monthly_free = monthly_income - monthly_exp
            annual_free = monthly_free * 12
            annual_contrib = inputs.monthly_investment_contribution * 12 * income_scale
            annual_savings_to_bank = max(0, annual_free - annual_contrib)

            savings += annual_savings_to_bank
            investments = (investments + annual_contrib) * (1 + inputs.investment_annual_return)
            net_worth = savings + investments

            rows.append({
                "year": year,
                "net_worth": round(net_worth, 2),
                "savings": round(savings, 2),
                "investments": round(investments, 2),
                "monthly_income": round(monthly_income, 2),
                "monthly_expenses": round(monthly_exp, 2),
            })
        return pd.DataFrame(rows)

    def run_monte_carlo(
        self,
        inputs: SimulationInputs,
        n_simulations: int = 1000,
        equity_std: float = 0.15,
    ) -> pd.DataFrame:
        rng = np.random.default_rng(seed=42)
        annual_return_mean = inputs.investment_annual_return

        # Shape: (n_simulations, simulation_years)
        returns = rng.normal(
            loc=annual_return_mean,
            scale=equity_std,
            size=(n_simulations, inputs.simulation_years),
        )

        # Vectorised simulation
        inv = np.full(n_simulations, inputs.current_investments_value, dtype=float)
        sav = np.full(n_simulations, inputs.current_savings, dtype=float)
        rows = []

        for year_idx in range(inputs.simulation_years):
            year = year_idx + 1
            income_scale = (1 + inputs.annual_salary_growth_rate) ** year
            exp_scale = (1 + inputs.inflation_rate) ** year
            monthly_free = (inputs.monthly_net_income * income_scale - inputs.monthly_expenses * exp_scale)
            annual_contrib = inputs.monthly_investment_contribution * 12 * income_scale
            annual_savings_to_bank = max(0, monthly_free * 12 - annual_contrib)

            inv = (inv + annual_contrib) * (1 + returns[:, year_idx])
            sav = sav + annual_savings_to_bank
            net_worth = inv + sav

            pcts = np.percentile(net_worth, [10, 25, 50, 75, 90])
            rows.append({
                "year": year,
                "p10": round(pcts[0], 2),
                "p25": round(pcts[1], 2),
                "p50": round(pcts[2], 2),
                "p75": round(pcts[3], 2),
                "p90": round(pcts[4], 2),
            })
        return pd.DataFrame(rows)

    def run_salary_scenarios(
        self,
        inputs: SimulationInputs,
        salary_growth_rates: list[float] | None = None,
    ) -> list[ScenarioResult]:
        rates = salary_growth_rates or [0.0, 0.03, 0.05, 0.08]
        results = []
        for rate in rates:
            modified = SimulationInputs(
                monthly_net_income=inputs.monthly_net_income,
                monthly_expenses=inputs.monthly_expenses,
                current_savings=inputs.current_savings,
                current_investments_value=inputs.current_investments_value,
                monthly_investment_contribution=inputs.monthly_investment_contribution,
                annual_salary_growth_rate=rate,
                investment_annual_return=inputs.investment_annual_return,
                inflation_rate=inputs.inflation_rate,
                simulation_years=inputs.simulation_years,
            )
            label = f"+{rate*100:.0f}% annuo"
            determ = self.run_deterministic(modified, label=label)
            mc = self.run_monte_carlo(modified)
            results.append(ScenarioResult(label=label, deterministic=determ, monte_carlo=mc))
        return results
