"""Portfolio service — materialise positions from investment transactions.

FIFO cost-basis accounting:
- For each (isin, broker) pair, replay all BUY and SELL transactions in
  date order to track net shares and average cost.
- Dividend / fee-only entries are skipped for cost-basis purposes.

All methods require user_id explicitly (prepared for multi-user).
"""

import logging
from collections import defaultdict
from typing import Any, Optional

import pandas as pd

logger = logging.getLogger(__name__)


class PortfolioService:
    def __init__(self, db):
        self._db = db

    # ------------------------------------------------------------------
    # Position recomputation
    # ------------------------------------------------------------------

    def recompute_positions(self, user_id: int, broker: Optional[str] = None) -> list[dict]:
        """Rebuild portfolio_positions from investment transactions (FIFO).

        Returns the list of upserted position dicts.
        """
        txs = self._db.get_investment_transactions(user_id, broker=broker)
        # group by (isin, broker)
        groups: dict[tuple, list] = defaultdict(list)
        for tx in txs:
            key = (tx.get("isin") or "", tx.get("source_bank") or "Unknown")
            groups[key].append(tx)

        results = []
        for (isin, broker_name), group in groups.items():
            if not isin:
                continue
            group.sort(key=lambda r: r["transaction_date"])
            net_shares, total_cost = self._fifo(group)
            avg_cost = (total_cost / net_shares) if net_shares else 0.0
            asset_name = (
                next((r.get("description", "") for r in group if r.get("description")), isin)
            )
            asset_type = next((r.get("asset_type") for r in group if r.get("asset_type")), None)
            ticker = self._db.get_isin_ticker(isin)

            pos = {
                "user_id": user_id,
                "isin": isin,
                "ticker": ticker,
                "asset_name": asset_name,
                "asset_type": asset_type,
                "broker": broker_name,
                "shares": net_shares,
                "avg_cost_per_share": avg_cost,
                "total_cost_basis": total_cost,
                "is_active": net_shares > 0.0001,
            }
            self._db.upsert_portfolio_position(pos)
            results.append(pos)
        return results

    def _fifo(self, transactions: list[dict]) -> tuple[float, float]:
        """Return (net_shares, total_cost_basis) from a sorted list of tx dicts."""
        net_shares = 0.0
        total_cost = 0.0
        for tx in transactions:
            amount = float(tx.get("amount") or 0)
            shares = float(tx.get("shares") or 0)
            fee = float(tx.get("fee") or 0)
            desc = (tx.get("description") or "").lower()
            tx_type = (tx.get("asset_type") or "")
            if shares == 0:
                continue
            # BUY: amount negative (cash out), shares positive
            if amount < 0 or "buy" in desc or "acquisto" in desc or "kauf" in desc:
                net_shares += abs(shares)
                total_cost += abs(amount) + fee
            # SELL: amount positive (cash in), shares negative
            elif amount > 0 or "sell" in desc or "vendita" in desc or "verkauf" in desc:
                sold = min(abs(shares), net_shares)
                avg = (total_cost / net_shares) if net_shares else 0
                net_shares -= sold
                total_cost -= avg * sold
                if net_shares < 1e-8:
                    net_shares = 0.0
                    total_cost = 0.0
        return max(net_shares, 0.0), max(total_cost, 0.0)

    # ------------------------------------------------------------------
    # Read positions
    # ------------------------------------------------------------------

    def get_positions(self, user_id: int) -> list[dict[str, Any]]:
        return self._db.get_portfolio_positions(user_id)

    def get_allocation_by_asset_class(self, user_id: int) -> pd.DataFrame:
        positions = self.get_positions(user_id)
        if not positions:
            return pd.DataFrame(columns=["asset_type", "value"])
        rows = []
        for p in positions:
            if not p.get("is_active"):
                continue
            price = p.get("current_price") or p.get("avg_cost_per_share") or 0
            value = float(p.get("shares", 0)) * float(price)
            rows.append({"asset_type": p.get("asset_type") or "unknown", "value": value})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.groupby("asset_type", as_index=False)["value"].sum()

    def get_allocation_by_broker(self, user_id: int) -> pd.DataFrame:
        positions = self.get_positions(user_id)
        if not positions:
            return pd.DataFrame(columns=["broker", "value"])
        rows = []
        for p in positions:
            if not p.get("is_active"):
                continue
            price = p.get("current_price") or p.get("avg_cost_per_share") or 0
            value = float(p.get("shares", 0)) * float(price)
            rows.append({"broker": p.get("broker") or "Unknown", "value": value})
        df = pd.DataFrame(rows)
        if df.empty:
            return df
        return df.groupby("broker", as_index=False)["value"].sum()
