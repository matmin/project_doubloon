"""P&L calculation — realised and unrealised gains/losses.

Realised P&L:
  For each SELL: (sell_price - avg_cost_at_time) * shares - fees - taxes.

Unrealised P&L:
  For each current position with live price:
  (current_price - avg_cost_per_share) * net_shares.

All methods return DataFrames suitable for direct display or Plotly.
"""

import logging
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


class PnLCalculator:
    def __init__(self, db):
        self._db = db

    # ------------------------------------------------------------------
    # Realised P&L
    # ------------------------------------------------------------------

    def compute_realized_pnl(self, user_id: int) -> pd.DataFrame:
        """Per-SELL transaction realised P&L.

        Returns DataFrame columns:
        transaction_date, isin, description, broker, shares_sold,
        sell_price, avg_cost, gross_pnl, fees, taxes, net_pnl
        """
        txs = self._db.get_investment_transactions(user_id)
        # Replay FIFO per (isin, broker) to track avg cost at each SELL
        from collections import defaultdict
        groups: dict[tuple, list] = defaultdict(list)
        for tx in txs:
            key = (tx.get("isin") or "", tx.get("source_bank") or "Unknown")
            groups[key].append(tx)

        rows = []
        for (isin, broker), group in groups.items():
            if not isin:
                continue
            group.sort(key=lambda r: r["transaction_date"])
            net_shares = 0.0
            total_cost = 0.0
            for tx in group:
                amount = float(tx.get("amount") or 0)
                shares = float(tx.get("shares") or 0)
                fee = float(tx.get("fee") or 0)
                tax = float(tx.get("tax") or 0)
                desc = (tx.get("description") or "").lower()
                if shares == 0:
                    continue
                if amount < 0 or any(w in desc for w in ("buy", "acquisto", "kauf")):
                    net_shares += abs(shares)
                    total_cost += abs(amount) + fee
                elif amount > 0 or any(w in desc for w in ("sell", "vendita", "verkauf")):
                    sold = min(abs(shares), net_shares)
                    avg = (total_cost / net_shares) if net_shares else 0
                    gross_pnl = (abs(amount) / sold - avg) * sold if sold else 0
                    rows.append({
                        "transaction_date": tx["transaction_date"],
                        "isin": isin,
                        "description": tx.get("description", ""),
                        "broker": broker,
                        "shares_sold": sold,
                        "sell_price": abs(amount) / sold if sold else 0,
                        "avg_cost": avg,
                        "gross_pnl": gross_pnl,
                        "fees": fee,
                        "taxes": tax,
                        "net_pnl": gross_pnl - fee - tax,
                    })
                    net_shares -= sold
                    total_cost -= avg * sold
                    if net_shares < 1e-8:
                        net_shares = 0.0
                        total_cost = 0.0
        if not rows:
            return pd.DataFrame(columns=[
                "transaction_date", "isin", "description", "broker",
                "shares_sold", "sell_price", "avg_cost",
                "gross_pnl", "fees", "taxes", "net_pnl",
            ])
        return pd.DataFrame(rows).sort_values("transaction_date", ascending=False)

    # ------------------------------------------------------------------
    # Unrealised P&L
    # ------------------------------------------------------------------

    def compute_unrealized_pnl(self, user_id: int) -> pd.DataFrame:
        """Per-position unrealised P&L using portfolio_positions current_price.

        Returns DataFrame columns:
        isin, asset_name, broker, shares, avg_cost, current_price,
        cost_basis, current_value, unrealized_pnl, unrealized_pnl_pct
        """
        positions = self._db.get_portfolio_positions(user_id)
        rows = []
        for pos in positions:
            if not pos.get("is_active"):
                continue
            shares = float(pos.get("shares") or 0)
            avg_cost = float(pos.get("avg_cost_per_share") or 0)
            current_price = float(pos.get("current_price") or 0)
            cost_basis = shares * avg_cost
            current_value = shares * current_price if current_price else None
            unr = (current_value - cost_basis) if current_value is not None else None
            unr_pct = (unr / cost_basis * 100) if (cost_basis and unr is not None) else None
            rows.append({
                "isin": pos.get("isin"),
                "asset_name": pos.get("asset_name"),
                "broker": pos.get("broker"),
                "shares": shares,
                "avg_cost": avg_cost,
                "current_price": current_price or None,
                "cost_basis": cost_basis,
                "current_value": current_value,
                "unrealized_pnl": unr,
                "unrealized_pnl_pct": unr_pct,
            })
        if not rows:
            return pd.DataFrame()
        return pd.DataFrame(rows)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------

    def compute_total_return(self, user_id: int) -> dict[str, Any]:
        """Aggregate: total invested, current value, realised + unrealised P&L."""
        real = self.compute_realized_pnl(user_id)
        unr = self.compute_unrealized_pnl(user_id)

        realized_pnl = float(real["net_pnl"].sum()) if not real.empty else 0.0
        total_invested = float(unr["cost_basis"].sum()) if not unr.empty else 0.0
        current_value_series = unr["current_value"].dropna() if not unr.empty else pd.Series([])
        current_value = float(current_value_series.sum()) if not current_value_series.empty else None
        unrealized_pnl = float(unr["unrealized_pnl"].dropna().sum()) if not unr.empty else None
        total_pnl = (
            realized_pnl + (unrealized_pnl or 0)
        ) if unrealized_pnl is not None else realized_pnl
        return_pct = (total_pnl / total_invested * 100) if total_invested else None

        return {
            "total_invested": total_invested,
            "current_value": current_value,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "total_pnl": total_pnl,
            "return_pct": return_pct,
        }
