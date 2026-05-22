"""ISIN → ticker resolution.

Priority order:
1. Built-in hardcoded map (zero latency, no network)
2. isin_ticker_cache table (DB cache of previous resolutions)
3. OpenFIGI API (free, no auth — https://api.openfigi.com/v3/mapping)

Returns None if resolution fails completely (so callers can skip price fetch).
"""

import logging
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Hardcoded map covers the most common EU-listed ETFs traded on XETRA/Euronext.
# ticker = Yahoo Finance symbol (with exchange suffix where needed).
KNOWN_ISIN_MAP: dict[str, str] = {
    # iShares Core MSCI World (accumulating)
    "IE00B4L5Y983": "IWDA.AS",
    # iShares Core MSCI World (distributing)
    "IE00B0M62Q58": "SWDA.L",
    # iShares MSCI Emerging Markets IMI
    "IE00BKM4GZ66": "EIMI.AS",
    # Vanguard FTSE All-World (accumulating)
    "IE00BK5BQT80": "VWCE.DE",
    # Vanguard FTSE All-World (distributing)
    "IE00B3RBWM25": "VWRL.AS",
    # Amundi MSCI World (accumulating)
    "LU1681043599": "CW8.PA",
    # Xtrackers MSCI World (accumulating)
    "IE00BJ0KDQ92": "XDWD.DE",
    # iShares Core S&P 500
    "IE0031442068": "CSPX.L",
    # Invesco S&P 500 (swap, acc)
    "IE00B3YCGJ38": "SPXS.L",
    # iShares Core Euro Stoxx 50 (acc)
    "IE00B53L3W79": "CS51.DE",
    # iShares MSCI Europe
    "IE00B4K48X80": "IMAE.AS",
    # Xtrackers Euro Stoxx 50
    "LU0274211217": "DXET.DE",
    # iShares Core Global Aggregate Bond
    "IE00B3F81409": "AGGG.L",
    # iShares Global Inflation Linked Bond
    "IE00B3F81K65": "IGIL.L",
    # Vanguard EUR Corporate Bond
    "IE00BZ163G84": "VECA.AS",
    # Physical Gold ETC (Xetra-Gold)
    "DE000A0S9GB0": "4GLD.DE",
    # WisdomTree Physical Gold
    "JE00B1VS3770": "PHAU.L",
    # iShares Core MSCI Pacific ex Japan
    "IE00B52MJY50": "CPXJ.L",
    # iShares Core MSCI Japan
    "IE00B4L5YX21": "IJPA.AS",
    # S&P 500 direct (for US accounts)
    "US78462F1030": "SPY",
    "US4642872422": "IVV",
    "US9229087690": "VTI",
    "US9229083632": "VT",
}

OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"


class ISINMapper:
    def __init__(self, db=None):
        self._db = db

    def resolve(self, isin: str) -> Optional[str]:
        """Return Yahoo Finance ticker for an ISIN, or None if unresolvable."""
        if not isin:
            return None

        # 1. Hardcoded map
        ticker = KNOWN_ISIN_MAP.get(isin.upper())
        if ticker:
            return ticker

        # 2. DB cache
        if self._db:
            cached = self._db.get_isin_ticker(isin)
            if cached:
                return cached

        # 3. OpenFIGI
        ticker = self._fetch_openfigi(isin)
        if ticker and self._db:
            self._db.save_isin_ticker(isin, ticker, source="openfigi")
        return ticker

    def _fetch_openfigi(self, isin: str) -> Optional[str]:
        try:
            resp = requests.post(
                OPENFIGI_URL,
                json=[{"idType": "ID_ISIN", "idValue": isin}],
                timeout=5,
            )
            if resp.status_code != 200:
                return None
            data = resp.json()
            if not data or not data[0].get("data"):
                return None
            # Prefer an entry with a ticker and exchCode XETRA/XNAS/XNYS
            entries = data[0]["data"]
            for preferred_exch in ("XETR", "XNAS", "XNYS", "XLON"):
                for e in entries:
                    if e.get("exchCode") == preferred_exch and e.get("ticker"):
                        return e["ticker"]
            # Fallback: first entry with a ticker
            for e in entries:
                if e.get("ticker"):
                    return e["ticker"]
        except Exception as exc:
            logger.debug("OpenFIGI lookup failed for %s: %s", isin, exc)
        return None
