"""Portfolio vs benchmark comparison.

Downloads benchmark price series via yfinance and normalises both the
portfolio and the benchmark to 100 at start_date.

Available benchmarks (Yahoo Finance symbols):
  S&P 500       → ^GSPC
  MSCI World    → IWDA.AS
  MSCI EM       → EIMI.AS
  Euro Stoxx 50 → ^STOXX50E
  BTP Italia    → BTPI.MI   (proxy)
"""

import logging
from datetime import date, timedelta
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

BENCHMARKS: dict[str, str] = {
    "S&P 500": "^GSPC",
    "MSCI World": "IWDA.AS",
    "MSCI Emerging Markets": "EIMI.AS",
    "Euro Stoxx 50": "^STOXX50E",
}

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False


class BenchmarkService:
    def __init__(self, db):
        self._db = db

    def get_portfolio_vs_benchmark(
        self,
        user_id: int,
        benchmark_label: str = "MSCI World",
        start_date: Optional[date] = None,
    ) -> Optional[pd.DataFrame]:
        """Return DataFrame indexed to 100 at start_date.

        Columns: date, portfolio, <benchmark_label>
        Returns None if data is insufficient.
        """
        if not _YF_AVAILABLE:
            logger.warning("yfinance not available; benchmark comparison skipped")
            return None

        if start_date is None:
            start_date = date.today() - timedelta(days=365)

        ticker = BENCHMARKS.get(benchmark_label)
        if not ticker:
            logger.warning("Unknown benchmark: %s", benchmark_label)
            return None

        # Portfolio daily value series from networth_snapshots
        snapshots = self._db.get_networth_snapshots(user_id, start_date=start_date.isoformat())
        if not snapshots or len(snapshots) < 2:
            logger.info("Not enough networth snapshots for benchmark comparison")
            return None

        port_df = pd.DataFrame(snapshots)[["snapshot_date", "investments_amount"]].copy()
        port_df["snapshot_date"] = pd.to_datetime(port_df["snapshot_date"])
        port_df = port_df.set_index("snapshot_date").sort_index()
        port_df.columns = ["portfolio"]

        # Benchmark series
        try:
            bm_raw = yf.download(
                ticker,
                start=start_date.isoformat(),
                progress=False,
                auto_adjust=True,
            )["Close"]
            if isinstance(bm_raw, pd.DataFrame):
                bm_raw = bm_raw.iloc[:, 0]
            bm_df = bm_raw.to_frame(name=benchmark_label)
        except Exception as exc:
            logger.warning("Benchmark download failed (%s): %s", ticker, exc)
            return None

        # Align on business-day intersection
        combined = port_df.join(bm_df, how="outer").ffill().dropna()
        if len(combined) < 2:
            return None

        # Rebase to 100
        for col in combined.columns:
            combined[col] = combined[col] / combined[col].iloc[0] * 100

        combined = combined.reset_index().rename(columns={"index": "date", "snapshot_date": "date"})
        return combined

    @staticmethod
    def available_benchmarks() -> list[str]:
        return list(BENCHMARKS.keys())
