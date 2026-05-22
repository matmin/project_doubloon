"""Live price fetcher with DB caching.

Uses yfinance for price data; falls back gracefully when offline or when the
ticker is unknown. Prices are cached in price_history (1 entry per day per
ISIN/ticker pair) so repeated calls within the same day don't hit the network.
"""

import logging
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import yfinance as yf
    _YF_AVAILABLE = True
except ImportError:
    _YF_AVAILABLE = False
    logger.warning("yfinance not installed; live prices unavailable")


class PriceFetcher:
    def __init__(self, db, isin_mapper):
        self._db = db
        self._mapper = isin_mapper

    def get_current_price(self, isin: str, ticker: Optional[str] = None) -> Optional[float]:
        """Return today's closing price for an ISIN/ticker. None on failure."""
        today = date.today().isoformat()

        # 1. DB cache hit
        cached = self._db.get_latest_price(isin)
        if cached and cached["price_date"] == today:
            return cached["price"]

        # 2. Resolve ticker
        resolved = ticker or (self._mapper.resolve(isin) if isin else None)
        if not resolved:
            logger.debug("Cannot resolve ticker for ISIN %s", isin)
            return None

        # 3. Fetch via yfinance
        price = self._fetch_yf(resolved)
        if price is not None and isin:
            self._db.save_price(isin, resolved, today, price)
        return price

    def refresh_all_positions(self, user_id: int) -> int:
        """Update current_price on all active portfolio_positions. Returns # updated."""
        positions = self._db.get_portfolio_positions(user_id)
        updated = 0
        for pos in positions:
            isin = pos.get("isin")
            ticker = pos.get("ticker")
            if not isin and not ticker:
                continue
            price = self.get_current_price(isin or "", ticker)
            if price is not None:
                self._db.update_position_price(pos["id"], price)
                updated += 1
        return updated

    def _fetch_yf(self, ticker: str) -> Optional[float]:
        if not _YF_AVAILABLE:
            return None
        try:
            info = yf.Ticker(ticker).fast_info
            price = getattr(info, "last_price", None) or getattr(info, "regularMarketPrice", None)
            if price:
                return float(price)
        except Exception as exc:
            logger.debug("yfinance fetch failed for %s: %s", ticker, exc)
        return None
