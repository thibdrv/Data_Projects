"""Scraping de books.toscrape.com (site d'entrainement) avec requests + Beautiful Soup.

Le site est statique : pas besoin de Selenium, c'est beaucoup plus rapide.
Le nettoyage (types, prix) est fait ici, à la source, et non dans des cellules à part.
"""
from __future__ import annotations

import re
import time
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .http import fetch, make_session, robots_allowed

BASE_URL = "https://books.toscrape.com/"
COLUMNS = ["url", "categorie", "titre", "prix_gbp", "stock", "note", "description", "upc", "date_collecte"]
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}


def parse_price(text: str) -> float | None:
    """'£51.77' (ou 'Â£51.77' si l'encodage est mal détecté) -> 51.77"""
    match = re.search(r"\d+(?:\.\d+)?", text)
    return float(match.group()) if match else None


def parse_stock(text: str) -> int | None:
    """'In stock (22 available)' -> 22"""
    match = re.search(r"\((\d+) available\)", text)
    return int(match.group(1)) if match else None


def parse_listing(html: str | bytes, page_url: str) -> tuple[list[str], str | None]:
    """URLs des livres d'une page de liste et URL de la page suivante (None sur la dernière)."""
    soup = BeautifulSoup(html, "html.parser")
    urls = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a")]
    next_link = soup.select_one("li.next a")
    return urls, (urljoin(page_url, next_link["href"]) if next_link else None)


def parse_book(html: str | bytes, url: str, today: str | None = None) -> dict:
    """Extrait les champs d'une fiche livre. La description est optionnelle (None si absente)."""
    soup = BeautifulSoup(html, "html.parser")  # bytes : l'encodage est détecté par BeautifulSoup

    crumbs = soup.select("ul.breadcrumb li a")
    description_title = soup.select_one("#product_description")
    description_p = description_title.find_next_sibling("p") if description_title else None
    rating_tag = soup.select_one("p.star-rating")
    rating_word = next((c for c in (rating_tag.get("class") or []) if c in RATINGS), None) if rating_tag else None
    upc_header = soup.find("th", string="UPC")
    upc_cell = upc_header.find_next_sibling("td") if upc_header else None

    def text_of(selector: str) -> str:
        tag = soup.select_one(selector)
        return tag.get_text(" ", strip=True) if tag else ""

    return {
        "url": url,
        "categorie": crumbs[-1].get_text(strip=True) if crumbs else None,
        "titre": text_of("h1") or None,
        "prix_gbp": parse_price(text_of(".price_color")),
        "stock": parse_stock(text_of(".instock.availability")),
        "note": RATINGS.get(rating_word),
        "description": description_p.get_text(" ", strip=True) if description_p else None,
        "upc": upc_cell.get_text(strip=True) if upc_cell else None,
        "date_collecte": today or date.today().isoformat(),
    }


def collect_book_urls(
    session: requests.Session,
    max_list_pages: int | None = None,
    delay: float = 0.3,
    sleep=time.sleep,
) -> list[str]:
    """ÉTAPE 1 : parcourt les pages de liste uniquement pour collecter les URLs des livres."""
    urls: list[str] = []
    page_url: str | None = BASE_URL
    pages = 0
    while page_url and (max_list_pages is None or pages < max_list_pages):
        page_urls, page_url = parse_listing(fetch(session, page_url).content, page_url)
        urls += page_urls
        pages += 1
        if page_url:
            sleep(delay)
    return urls


def scrape_books(
    session: requests.Session | None = None,
    max_books: int | None = None,
    delay: float = 0.3,
    checkpoint: str | Path | None = None,
    save_every: int = 50,
    check_robots: bool = True,
    sleep=time.sleep,
) -> pd.DataFrame:
    """ÉTAPE 1 : collecte des URLs. ÉTAPE 2 : visite directe de chaque fiche.

    checkpoint  fichier CSV écrit toutes les `save_every` fiches ; les URLs déjà présentes
                sont ignorées, ce qui permet de reprendre après une interruption.
    Les URLs en erreur sont listées dans `df.attrs["urls_en_erreur"]`.
    """
    session = session or make_session()
    if check_robots and not robots_allowed(BASE_URL, session):
        raise PermissionError(f"robots.txt interdit l'accès à {BASE_URL}")

    rows: list[dict] = []
    checkpoint = Path(checkpoint) if checkpoint else None
    if checkpoint and checkpoint.exists():
        saved = pd.read_csv(checkpoint)
        rows = saved.astype(object).where(saved.notna(), None).to_dict("records")
        print(f"Reprise : {len(rows)} livres déjà enregistrés")
    done = {row["url"] for row in rows}

    def save() -> None:
        if checkpoint:
            checkpoint.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows, columns=COLUMNS).to_csv(checkpoint, index=False, encoding="utf-8")

    urls = collect_book_urls(session, delay=delay, sleep=sleep)
    print(f"{len(urls)} URLs collectées")
    if max_books is not None:
        urls = urls[:max_books]

    errors: list[str] = []
    new = 0
    for url in urls:
        if url in done:
            continue
        try:
            rows.append(parse_book(fetch(session, url).content, url))
        except requests.RequestException as error:
            errors.append(url)
            print(f"Erreur sur {url} : {type(error).__name__}")
        new += 1
        if new % save_every == 0:
            save()
        sleep(delay)
    save()

    df = pd.DataFrame(rows, columns=COLUMNS)
    df.attrs["urls_en_erreur"] = errors
    print(f"{len(df)} lignes enregistrées, {len(errors)} erreurs")
    return df


def add_euro_prices(df: pd.DataFrame, rate: float) -> pd.DataFrame:
    """Ajoute `taux_gbp_eur` et `prix_eur` (arrondi à 2 décimales), sans modifier `df`."""
    out = df.copy()
    out["taux_gbp_eur"] = rate
    out["prix_eur"] = (out["prix_gbp"] * rate).round(2)
    return out
