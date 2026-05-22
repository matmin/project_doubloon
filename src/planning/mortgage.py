"""Mortgage simulator."""

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class MortgageResult:
    monthly_payment: float
    total_interest: float
    total_cost: float
    ltv_pct: float
    can_afford: bool
    months_to_down_payment: Optional[int]
    amortization: pd.DataFrame


class MortgageSimulator:

    def simulate(
        self,
        property_price: float,
        down_payment_pct: float,
        annual_rate: float,
        duration_years: int,
        monthly_net_income: float,
        current_savings: float = 0.0,
        monthly_savings_rate: float = 0.0,
    ) -> MortgageResult:
        down_payment = property_price * down_payment_pct / 100
        principal = property_price - down_payment
        ltv = principal / property_price * 100
        monthly_rate = annual_rate / 100 / 12
        n = duration_years * 12

        if monthly_rate == 0:
            monthly_payment = principal / n
        else:
            monthly_payment = principal * monthly_rate * (1 + monthly_rate) ** n / ((1 + monthly_rate) ** n - 1)

        total_cost = monthly_payment * n
        total_interest = total_cost - principal
        can_afford = (monthly_payment / monthly_net_income) <= 0.33 if monthly_net_income > 0 else False

        # Months to accumulate down payment from current savings
        months_to_down: Optional[int] = None
        if current_savings < down_payment and monthly_savings_rate > 0:
            gap = down_payment - current_savings
            months_to_down = math.ceil(gap / monthly_savings_rate)

        # Build amortisation schedule
        rows = []
        balance = principal
        for m in range(1, n + 1):
            interest = balance * monthly_rate if monthly_rate else 0
            principal_paid = monthly_payment - interest
            balance -= principal_paid
            balance = max(balance, 0.0)
            rows.append({
                "month": m,
                "payment": round(monthly_payment, 2),
                "principal": round(principal_paid, 2),
                "interest": round(interest, 2),
                "balance": round(balance, 2),
            })

        return MortgageResult(
            monthly_payment=round(monthly_payment, 2),
            total_interest=round(total_interest, 2),
            total_cost=round(total_cost, 2),
            ltv_pct=round(ltv, 2),
            can_afford=can_afford,
            months_to_down_payment=months_to_down,
            amortization=pd.DataFrame(rows),
        )
