"""Tests de parsing sur du HTML fixe : aucun acces reseau."""
from webscraping import books, chucknorris, github_api

CHUCK_PAGE = """
<div class="card-body"><p class="card-text">Premier fait.</p></div>
<div class="card-body"><p class="card-text"></p></div>
<div class="card-body"><p class="card-text">Ligne 1<br/>Ligne 2</p></div>
<ul class="pagination">
  <li><a class="page-link" href="/facts/top/2">&gt;&gt;</a></li>
  <li><a class="page-link" href="/facts/top/528">Dernier</a></li>
</ul>
"""

CHUCK_LAST_PAGE = """
<p class="card-text">Dernier fait.</p>
<ul class="pagination"><li><a class="page-link" href="/facts/top/527">&lt;&lt;</a></li></ul>
"""

LISTING = """
<article class="product_pod"><h3><a href="catalogue/a-light-in-the-attic_1000/index.html">A Light</a></h3></article>
<article class="product_pod"><h3><a href="catalogue/tipping-the-velvet_999/index.html">Tipping</a></h3></article>
<ul class="pager"><li class="next"><a href="catalogue/page-2.html">next</a></li></ul>
"""

BOOK = """
<ul class="breadcrumb">
  <li><a href="/">Home</a></li><li><a href="/books">Books</a></li>
  <li><a href="/poetry">Poetry</a></li><li class="active">A Light in the Attic</li>
</ul>
<h1>A Light in the Attic</h1>
<p class="price_color">£51.77</p>
<p class="instock availability"> In stock (22 available) </p>
<p class="star-rating Three"></p>
<div id="product_description"><h2>Product Description</h2></div>
<p>It's hard to imagine a world without A Light in the Attic.</p>
<table><tr><th>UPC</th><td>a897fe39b1053632</td></tr></table>
"""

BOOK_NO_DESCRIPTION = BOOK.replace('<div id="product_description"><h2>Product Description</h2></div>', "")


def test_parse_page_extracts_facts_and_next_link():
    facts, next_url = chucknorris.parse_page(CHUCK_PAGE)
    assert facts == ["Premier fait.", "Ligne 1 Ligne 2"]  # <p> vide ignore, <br/> remplace par un espace
    assert next_url == "https://www.chucknorrisfacts.fr/facts/top/2"


def test_parse_page_last_page_has_no_next():
    facts, next_url = chucknorris.parse_page(CHUCK_LAST_PAGE)
    assert facts == ["Dernier fait."]
    assert next_url is None


def test_parse_listing_returns_absolute_urls():
    urls, next_url = books.parse_listing(LISTING, "https://books.toscrape.com/")
    assert urls == [
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
    ]
    assert next_url == "https://books.toscrape.com/catalogue/page-2.html"


def test_parse_listing_last_page():
    _, next_url = books.parse_listing("<article class='product_pod'></article>", "https://books.toscrape.com/catalogue/page-50.html")
    assert next_url is None


def test_parse_book_extracts_typed_fields():
    row = books.parse_book(BOOK, "https://books.toscrape.com/x", today="2026-01-01")
    assert row == {
        "url": "https://books.toscrape.com/x",
        "categorie": "Poetry",
        "titre": "A Light in the Attic",
        "prix_gbp": 51.77,
        "stock": 22,
        "note": 3,
        "description": "It's hard to imagine a world without A Light in the Attic.",
        "upc": "a897fe39b1053632",
        "date_collecte": "2026-01-01",
    }


def test_parse_book_without_description_keeps_the_row():
    row = books.parse_book(BOOK_NO_DESCRIPTION, "u")
    assert row["description"] is None
    assert row["titre"] == "A Light in the Attic"


def test_parse_price_handles_mojibake_currency():
    assert books.parse_price("Â£51.77") == 51.77
    assert books.parse_price("pas de prix") is None


def test_parse_stock():
    assert books.parse_stock("In stock (1 available)") == 1
    assert books.parse_stock("Out of stock") is None


def test_add_euro_prices_does_not_mutate_input():
    import pandas as pd

    df = pd.DataFrame({"prix_gbp": [10.0, 51.77]})
    out = books.add_euro_prices(df, 1.2)
    assert out["prix_eur"].tolist() == [12.0, 62.12]
    assert out["taux_gbp_eur"].tolist() == [1.2, 1.2]
    assert "prix_eur" not in df.columns


def test_github_parse_repo_keeps_only_repo_metadata():
    item = {
        "name": "pandas",
        "stargazers_count": 40000,
        "forks_count": 16000,
        "language": "Python",
        "open_issues_count": 3000,
        "archived": False,
        "created_at": "2010-08-24T01:37:33Z",
        "pushed_at": "2026-01-01T00:00:00Z",
        "owner": {"login": "pandas-dev", "email": "ne-doit-pas-etre-copie"},
    }
    row = github_api.parse_repo(item)
    assert row["nom"] == "pandas" and row["etoiles"] == 40000 and row["langage"] == "Python"
    assert set(row) == set(github_api.COLUMNS)
