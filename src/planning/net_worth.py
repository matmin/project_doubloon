"""Net worth projector — combines DB snapshots with forward projection."""

import pandas as pd

from .engine import SimulationInputs


class NetWorthProjector:
    def __init__(self, db):
        self._db = db

    def get_historical(self, user_id: int) -> pd.DataFrame:
        """Return historical networth_snapshots as a clean DataFrame."""
        snaps = self._db.get_networth_snapshots(user_id, limit=500)
        if not snaps:
            return pd.DataFrame(columns=["date", "net_worth", "cash", "investments"])
        df = pd.DataFrame(snaps)
        df["date"] = pd.to_datetime(df["snapshot_date"])
        return df[["date", "net_worth", "cash_amount", "investments_amount"]].rename(
            columns={"cash_amount": "cash", "investments_amount": "investments"}
        ).sort_values("date")

    def project_forward(
        self,
        inputs: SimulationInputs,
        years: int | None = None,
    ) -> pd.DataFrame:
        """Simple deterministic projection from today's net worth."""
        from .scenarios import ScenarioRunner
        runner = ScenarioRunner()
        n = years or inputs.simulation_years
        modified = SimulationInputs(
            monthly_net_income=inputs.monthly_net_income,
            monthly_expenses=inputs.monthly_expenses,
            current_savings=inputs.current_savings,
            current_investments_value=inputs.current_investments_value,
            monthly_investment_contribution=inputs.monthly_investment_contribution,
            annual_salary_growth_rate=inputs.annual_salary_growth_rate,
            investment_annual_return=inputs.investment_annual_return,
            inflation_rate=inputs.inflation_rate,
            simulation_years=n,
        )
        return runner.run_deterministic(modified)
