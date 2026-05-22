"""PlanningEngine — orchestration and auto-population from DB history."""

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Optional


@dataclass
class SimulationInputs:
    monthly_net_income: float
    monthly_expenses: float
    current_savings: float
    current_investments_value: float
    monthly_investment_contribution: float
    annual_salary_growth_rate: float = 0.03
    investment_annual_return: float = 0.07
    inflation_rate: float = 0.025
    simulation_years: int = 30
    # optional context
    monthly_savings: float = field(init=False)

    def __post_init__(self):
        self.monthly_savings = self.monthly_net_income - self.monthly_expenses


class PlanningEngine:
    def __init__(self, db):
        self._db = db

    def get_inputs_from_history(
        self,
        user_id: int,
        lookback_months: int = 6,
    ) -> SimulationInputs:
        """Auto-populate SimulationInputs from the last N months of transactions."""
        end = date.today()
        start = end - timedelta(days=lookback_months * 30)
        txs = self._db.get_transactions(
            user_id=user_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
            limit=10000,
        )

        income, expenses = 0.0, 0.0
        for tx in txs:
            tx_type = (tx.get("transaction_type") or "expense").lower()
            if tx_type in ("investment", "transfer"):
                continue
            amount = float(tx.get("amount") or 0)
            if amount > 0:
                income += amount
            else:
                expenses += abs(amount)

        months = max(lookback_months, 1)
        avg_income = income / months
        avg_expenses = expenses / months
        avg_contribution = avg_income * 0.2  # default 20% of income if no investment data

        # Try to get investment contribution from actual investment transactions
        inv_txs = self._db.get_investment_transactions(
            user_id,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )
        if inv_txs:
            total_invested = sum(abs(float(t.get("amount") or 0)) for t in inv_txs if float(t.get("amount") or 0) < 0)
            avg_contribution = total_invested / months

        # Current portfolio value from positions
        positions = self._db.get_portfolio_positions(user_id)
        portfolio_value = 0.0
        for pos in positions:
            if pos.get("is_active"):
                shares = float(pos.get("shares") or 0)
                price = float(pos.get("current_price") or pos.get("avg_cost_per_share") or 0)
                portfolio_value += shares * price

        # Current savings from latest networth snapshot
        snaps = self._db.get_networth_snapshots(user_id, limit=1)
        current_savings = float(snaps[0]["cash_amount"]) if snaps else 0.0

        return SimulationInputs(
            monthly_net_income=round(avg_income, 2),
            monthly_expenses=round(avg_expenses, 2),
            current_savings=round(current_savings, 2),
            current_investments_value=round(portfolio_value, 2),
            monthly_investment_contribution=round(avg_contribution, 2),
        )
