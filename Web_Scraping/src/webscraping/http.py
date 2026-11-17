"""Outils HTTP communs : session avec retry, User-Agent et robots.txt."""
from __future__ import annotations

from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "Mozilla/5.0 (exercice pedagogique de web scraping)"
TIMEOUT = 10  # secondes

_robots_cache: dict[str, RobotFileParser] = {}


def make_session(user_agent: str = USER_AGENT, retries: int = 3, backoff: float = 1.0) -> requests.Session:
    """Session `requests` qui réessaie automatiquement les erreurs temporaires.

    Les codes 429 (trop de requêtes) et 5xx sont rejoués avec un délai croissant
    (backoff * 2**n secondes) ; l'en-tête Retry-After du serveur est respecté.
    """
    retry = Retry(
        total=retries,
        backoff_factor=backoff,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "HEAD"),
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers["User-Agent"] = user_agent
    return session


def fetch(session: requests.Session, url: str, timeout: float = TIMEOUT) -> requests.Response:
    """GET avec timeout ; lève une exception si le serveur répond 4xx/5xx."""
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    return response


def _load_robots(root: str, session: requests.Session) -> RobotFileParser:
    parser = RobotFileParser()
    response = session.get(root + "/robots.txt", timeout=TIMEOUT)
    content_type = response.headers.get("Content-Type", "").lower()
    if response.status_code == 200 and "html" not in content_type:
        parser.parse(response.text.splitlines())
    elif response.status_code in (401, 403):
        parser.disallow_all = True  # accès refusé au robots.txt : on s'abstient
    else:
        # 404 (ou page HTML d'erreur) : pas de robots.txt, aucune restriction
        parser.parse([])
    return parser


def robots_allowed(url: str, session: requests.Session | None = None, user_agent: str = USER_AGENT) -> bool:
    """Indique si robots.txt autorise `user_agent` à récupérer `url`."""
    parts = urlsplit(url)
    root = f"{parts.scheme}://{parts.netloc}"
    parser = _robots_cache.get(root)
    if parser is None:
        parser = _load_robots(root, session or make_session(user_agent))
        _robots_cache[root] = parser
    return parser.can_fetch(user_agent, url)
