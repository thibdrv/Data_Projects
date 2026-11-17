"""Crawl paginé de chucknorrisfacts.fr (requests + Beautiful Soup)."""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .http import fetch, make_session, robots_allowed

BASE_URL = "https://www.chucknorrisfacts.fr"
COLUMNS = ["page", "fait"]


def page_url(number: int) -> str:
    return f"{BASE_URL}/facts/top/{number}"


def parse_page(html: str) -> tuple[list[str], str | None]:
    """Extrait les faits d'une page et l'URL de la page suivante (None sur la dernière)."""
    soup = BeautifulSoup(html, "html.parser")
    # get_text(" ", strip=True) : sépare les <br/> par un espace et nettoie le texte
    facts = [p.get_text(" ", strip=True) for p in soup.find_all("p", class_="card-text")]
    facts = [fact for fact in facts if fact]  # ignore les <p> vides
    next_href = next(
        (a.get("href") for a in soup.find_all("a", class_="page-link") if a.text.strip() == ">>"),
        None,
    )
    return facts, (BASE_URL + next_href if next_href else None)


def scrape_page(url: str, session: requests.Session | None = None) -> tuple[list[str], str | None]:
    """Télécharge une page et retourne (faits, URL de la page suivante ou None)."""
    return parse_page(fetch(session or make_session(), url).text)


def crawl(
    max_pages: int | None = None,
    start_page: int = 1,
    session: requests.Session | None = None,
    delay: float = 1.0,
    checkpoint: str | Path | None = None,
    save_every: int = 10,
    check_robots: bool = True,
    sleep=time.sleep,
) -> pd.DataFrame:
    """Suit le lien ">>" de page en page et retourne un DataFrame (page, fait).

    max_pages   nombre de pages à télécharger dans cet appel (None : jusqu'à la dernière)
    checkpoint  fichier CSV écrit toutes les `save_every` pages ; s'il existe déjà,
                le crawl reprend après la dernière page enregistrée
    """
    session = session or make_session()
    first_url = page_url(start_page)
    if check_robots and not robots_allowed(first_url, session):
        raise PermissionError(f"robots.txt interdit l'accès à {first_url}")

    rows: list[dict] = []
    resumed = False
    checkpoint = Path(checkpoint) if checkpoint else None
    if checkpoint and checkpoint.exists():
        saved = pd.read_csv(checkpoint)
        if not saved.empty:
            rows = saved.to_dict("records")
            start_page = int(saved["page"].max()) + 1
            resumed = True
            print(f"Reprise après la page {start_page - 1} ({len(rows)} faits déjà enregistrés)")

    def save() -> None:
        if checkpoint:
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows, columns=COLUMNS).to_csv(checkpoint, index=False, encoding="utf-8")

    url: str | None = page_url(start_page)
    page, done = start_page, 0
    while url and (max_pages is None or done < max_pages):
        try:
            facts, url = scrape_page(url, session)
        except requests.HTTPError as error:
            if resumed and error.response is not None and error.response.status_code == 404:
                print("Crawl déjà terminé : plus de page après la dernière enregistrée")
                break
            raise
        rows += [{"page": page, "fait": fact} for fact in facts]
        print(f"Page {page} : {len(facts)} faits")
        page, done = page + 1, done + 1
        if done % save_every == 0:
            save()
        if url:
            sleep(delay)
    save()
    return pd.DataFrame(rows, columns=COLUMNS)
