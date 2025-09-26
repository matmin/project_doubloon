from typing import Any, Dict, Iterable, Protocol


class TransactionProvider(Protocol):
    name: str
    bank_label: str

    def parse(self, file_obj) -> Iterable[Dict[str, Any]]: ...


PROVIDERS = {}


def register_provider(provider: TransactionProvider):
    PROVIDERS[provider.name] = provider
