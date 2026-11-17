"""Exemple avec l'API officielle de GitHub : l'alternative recommandée au scraping.

On ne lit ici que des métadonnées publiques de dépôts d'une organisation
(nom, étoiles, langage...). Aucune donnée personnelle n'est collectée.
Sans jeton, l'API autorise 60 requêtes par heure ; avec la variable d'environnement
GITHUB_TOKEN, 5000. Ne mettez jamais un jeton dans le code ou dans un notebook.
"""
from __future__ import annotations

import os

import pandas as pd
import requests

from .http import TIMEOUT, make_session

API_URL = "https://api.github.com"
COLUMNS = ["nom", "etoiles", "forks", "langage", "issues_ouvertes", "archive", "cree_le", "mis_a_jour_le"]


def parse_repo(item: dict) -> dict:
    """Ne garde que les métadonnées du dépôt utiles à l'analyse."""
    return {
        "nom": item.get("name"),
        "etoiles": item.get("stargazers_count", 0),
        "forks": item.get("forks_count", 0),
        "langage": item.get("language"),
        "issues_ouvertes": item.get("open_issues_count", 0),
        "archive": bool(item.get("archived", False)),
        "cree_le": item.get("created_at"),
        "mis_a_jour_le": item.get("pushed_at"),
    }


def fetch_org_repos(
    org: str,
    session: requests.Session | None = None,
    token: str | None = None,
    max_pages: int = 3,
    per_page: int = 100,
) -> pd.DataFrame:
    """Dépôts publics d'une organisation, en respectant la limite de requêtes de l'API."""
    token = token or os.environ.get("GITHUB_TOKEN")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    session = session or make_session()

    rows: list[dict] = []
    for page in range(1, max_pages + 1):
        response = session.get(
            f"{API_URL}/orgs/{org}/repos",
            params={"type": "public", "per_page": per_page, "page": page},
            headers=headers,
            timeout=TIMEOUT,
        )
        if response.status_code in (403, 429) and response.headers.get("X-RateLimit-Remaining") == "0":
            reset = response.headers.get("X-RateLimit-Reset", "inconnu")
            raise RuntimeError(f"Limite de requêtes GitHub atteinte (réinitialisation : timestamp {reset})")
        response.raise_for_status()
        batch = response.json()
        rows += [parse_repo(item) for item in batch]
        if len(batch) < per_page:
            break
    return pd.DataFrame(rows, columns=COLUMNS)
