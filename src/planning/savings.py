"""Savings projection and FIRE calculator."""

import math
from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class SavingsProjection:
    years: int
    final_value: float
    timeline: pd.DataFrame  # year, value


@dataclass
class FireResult:
    fire_number: float
    years_to_fire: Optional[float]
    monthly_contribution_needed: float
    safe_withdrawal_rate: float
    timeline: pd.DataFrame  # year, portfolio_value, target


class FireCalculator:

    def compute(
        self,
        current_portfolio: float,
        monthly_contribution: float,
        annual_return: float = 0.07,
        safe_withdrawal_rate: float = 0.04,
        annual_expenses: Optional[float] = None,
        fire_multiple: float = 25.0,
    ) -> FireResult:
        if annual_expenses is None:
            # derive from FIRE number (circular if both unknown → use 25 multiple of monthly)
            annual_expenses = monthly_contribution * 12

        fire_number = annual_expenses * fire_multiple
        monthly_return = annual_return / 12
        years_to_fire: Optional[float] = None
        rows = []

        value = current_portfolio
        for year in range(1, 61):
            for _ in range(12):
                value = value * (1 + monthly_return) + monthly_contribution
            rows.append({"year": year, "portfolio_value": round(value, 2), "fire_target": round(fire_number, 2)})
            if years_to_fire is None and value >= fire_number:
                years_to_fire = year

        # Monthly contribution needed (if not already on track)
        if current_portfolio >= fire_number:
            needed = 0.0
        elif annual_return > 0:
            # FV = PV*(1+r)^n + PMT * ((1+r)^n - 1) / r  → solve for PMT
            r = monthly_return
            n = 30 * 12
            needed_pmt = (fire_number - current_portfolio * (1 + r) ** n) * r / ((1 + r) ** n - 1)
            needed = max(0.0, needed_pmt)
        else:
            needed = max(0.0, (fire_number - current_portfolio) / (30 * 12))

        return FireResult(
            fire_number=round(fire_number, 2),
            years_to_fire=years_to_fire,
            monthly_contribution_needed=round(needed, 2),
            safe_withdrawal_rate=safe_withdrawal_rate,
            timeline=pd.DataFrame(rows),
        )

    def project_savings(
        self,
        current_savings: float,
        monthly_contribution: float,
        annual_return: float,
        years: int,
    ) -> SavingsProjection:
        monthly_return = annual_return / 12
        value = current_savings
        rows = []
        for year in range(1, years + 1):
            for _ in range(12):
                value = value * (1 + monthly_return) + monthly_contribution
            rows.append({"year": year, "value": round(value, 2)})
        return SavingsProjection(
            years=years,
            final_value=round(value, 2),
            timeline=pd.DataFrame(rows),
        )
