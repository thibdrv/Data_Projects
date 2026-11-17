"""Taux de change GBP -> EUR depuis une API publique, avec valeur de secours."""
from __future__ import annotations

from dataclasses import dataclass

import requests

from .http import TIMEOUT, make_session

API_URL = "https://api.frankfurter.dev/v1/latest"
FALLBACK_RATE = 1.16  # utilisé si l'API est injoignable (valeur approximative)


@dataclass(frozen=True)
class FxRate:
    rate: float
    date: str | None  # date du taux fourni par l'API ; None pour la valeur de secours
    source: str  # "frankfurter" ou "fallback"


def get_gbp_eur(session: requests.Session | None = None, fallback: float = FALLBACK_RATE) -> FxRate:
    """Retourne le dernier taux GBP -> EUR et sa date (données de la BCE via frankfurter.dev)."""
    try:
        response = (session or make_session()).get(
            API_URL, params={"base": "GBP", "symbols": "EUR"}, timeout=TIMEOUT
        )
        response.raise_for_status()
        payload = response.json()
        return FxRate(rate=float(payload["rates"]["EUR"]), date=payload["date"], source="frankfurter")
    except (requests.RequestException, KeyError, TypeError, ValueError):
        return FxRate(rate=fallback, date=None, source="fallback")
