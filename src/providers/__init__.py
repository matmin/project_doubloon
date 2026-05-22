from .amex_csv import AmexCSVProvider
from .base import PROVIDERS, register_provider
from .bbva_csv import BBVACSVProvider
from .intesa_excel import IntesaExcelProvider
from .revolut_csv import RevolutCSVProvider, RevolutInvestExcelProvider
from .scalable_csv import ScalableCSVProvider
from .trade_republic_csv import TradeRepublicCSVProvider


def register_all_providers() -> None:
    """Register every known provider in the global PROVIDERS registry."""
    for p in (
        IntesaExcelProvider(),
        AmexCSVProvider(),
        TradeRepublicCSVProvider(),
        ScalableCSVProvider(),
        RevolutCSVProvider(),
        RevolutInvestExcelProvider(),
        BBVACSVProvider(),
    ):
        register_provider(p)


__all__ = [
    "PROVIDERS",
    "register_provider",
    "register_all_providers",
    "IntesaExcelProvider",
    "AmexCSVProvider",
    "TradeRepublicCSVProvider",
    "ScalableCSVProvider",
    "RevolutCSVProvider",
    "RevolutInvestExcelProvider",
    "BBVACSVProvider",
]
