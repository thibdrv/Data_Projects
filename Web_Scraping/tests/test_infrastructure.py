"""Tests de la session HTTP, de robots.txt, du crawl avec reprise, du taux de change,
de la validation et de l'export. Les reponses reseau sont simulees."""
import sqlite3

import pandas as pd
import pytest
import requests

from webscraping import chucknorris, fx, http, storage, validation


class FakeResponse:
    def __init__(self, text="", status=200, headers=None, payload=None):
        self.text = text
        self.content = text.encode("utf-8")
        self.status_code = status
        self.headers = headers or {}
        self._payload = payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)

    def json(self):
        return self._payload


class FakeSession:
    """Session factice : `routes` associe une URL a une reponse ; chaque appel est memorise."""

    def __init__(self, routes):
        self.routes = routes
        self.calls = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        return self.routes.get(url, FakeResponse(status=404))


# ------------------------------------------------------------------ session / robots
def test_session_retries_temporary_errors_and_sets_user_agent():
    session = http.make_session(retries=4)
    retry = session.get_adapter("https://example.com").max_retries
    assert retry.total == 4
    assert 429 in retry.status_forcelist and 503 in retry.status_forcelist
    assert session.headers["User-Agent"] == http.USER_AGENT


@pytest.fixture(autouse=True)
def clear_robots_cache():
    http._robots_cache.clear()


def test_robots_respects_disallow_rules():
    robots = "User-agent: *\nDisallow: /prive/\n"
    session = FakeSession({"https://site.test/robots.txt": FakeResponse(robots, headers={"Content-Type": "text/plain"})})
    assert http.robots_allowed("https://site.test/public/page", session) is True
    assert http.robots_allowed("https://site.test/prive/page", session) is False
    assert session.calls == ["https://site.test/robots.txt"]  # robots.txt n'est telecharge qu'une fois


def test_robots_404_or_html_means_no_restriction():
    session = FakeSession({"https://a.test/robots.txt": FakeResponse("<html>404</html>", status=404)})
    assert http.robots_allowed("https://a.test/n-importe-quoi", session) is True
    session = FakeSession({"https://b.test/robots.txt": FakeResponse("<html>page</html>", headers={"Content-Type": "text/html"})})
    assert http.robots_allowed("https://b.test/x", session) is True


def test_robots_403_disallows_everything():
    session = FakeSession({"https://c.test/robots.txt": FakeResponse(status=403)})
    assert http.robots_allowed("https://c.test/x", session) is False


# ------------------------------------------------------------------ crawl + reprise
def chuck_page(number, last):
    nav = "" if number == last else f'<a class="page-link" href="/facts/top/{number + 1}">&gt;&gt;</a>'
    return FakeResponse(f'<p class="card-text">Fait {number}a</p><p class="card-text">Fait {number}b</p>{nav}')


def chuck_session(last=5):
    routes = {"https://www.chucknorrisfacts.fr/robots.txt": FakeResponse(status=404)}
    routes.update({chucknorris.page_url(n): chuck_page(n, last) for n in range(1, last + 1)})
    return FakeSession(routes)


def test_crawl_follows_next_links_until_the_last_page():
    session = chuck_session(last=3)
    sleeps = []
    df = chucknorris.crawl(session=session, sleep=sleeps.append, delay=2)
    assert df["page"].tolist() == [1, 1, 2, 2, 3, 3]
    assert len(sleeps) == 2 and set(sleeps) == {2}  # pas de pause apres la derniere page


def test_crawl_resumes_from_checkpoint(tmp_path):
    checkpoint = tmp_path / "faits.csv"
    chucknorris.crawl(max_pages=2, session=chuck_session(5), sleep=lambda s: None, checkpoint=checkpoint, save_every=1)
    assert pd.read_csv(checkpoint)["page"].max() == 2

    session = chuck_session(5)
    df = chucknorris.crawl(session=session, sleep=lambda s: None, checkpoint=checkpoint)
    assert df["page"].tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
    assert chucknorris.page_url(1) not in session.calls and chucknorris.page_url(2) not in session.calls


def test_crawl_on_finished_checkpoint_is_a_noop(tmp_path):
    checkpoint = tmp_path / "faits.csv"
    chucknorris.crawl(session=chuck_session(2), sleep=lambda s: None, checkpoint=checkpoint)
    df = chucknorris.crawl(session=chuck_session(2), sleep=lambda s: None, checkpoint=checkpoint)
    assert df["page"].max() == 2  # la page 3 n'existe pas (404) : fin normale


def test_crawl_refuses_when_robots_disallows():
    session = FakeSession({"https://www.chucknorrisfacts.fr/robots.txt": FakeResponse("User-agent: *\nDisallow: /", headers={"Content-Type": "text/plain"})})
    with pytest.raises(PermissionError):
        chucknorris.crawl(session=session)


# ------------------------------------------------------------------ taux de change
def test_fx_returns_api_rate():
    payload = {"base": "GBP", "date": "2026-11-16", "rates": {"EUR": 1.1983}}
    session = FakeSession({fx.API_URL: FakeResponse(payload=payload)})
    assert fx.get_gbp_eur(session) == fx.FxRate(1.1983, "2026-11-16", "frankfurter")


def test_fx_falls_back_when_api_fails():
    class Boom:
        def get(self, *a, **k):
            raise requests.ConnectionError("hors ligne")

    result = fx.get_gbp_eur(Boom())
    assert result == fx.FxRate(fx.FALLBACK_RATE, None, "fallback")
    assert fx.get_gbp_eur(FakeSession({fx.API_URL: FakeResponse(payload={"oops": 1})})).source == "fallback"


# ------------------------------------------------------------------ validation
def valid_books(n=3):
    return pd.DataFrame(
        {
            "url": [f"u{i}" for i in range(n)],
            "categorie": ["Poetry"] * n,
            "titre": [f"t{i}" for i in range(n)],
            "prix_gbp": [10.0 + i for i in range(n)],
            "stock": [1] * n,
            "note": [3] * n,
            "description": [None] * n,  # une description manquante est acceptee
        }
    )


def test_validation_accepts_clean_data_with_missing_descriptions():
    assert validation.validate_books(valid_books(), expected_rows=3) == []


def test_validation_reports_every_problem():
    df = valid_books()
    df.loc[0, "titre"] = None
    df.loc[1, "prix_gbp"] = 150.0
    df.loc[2, "note"] = 9
    df.loc[2, "url"] = "u0"
    problems = " | ".join(validation.validate_books(df, expected_rows=1000))
    assert "3 lignes au lieu de 1000" in problems
    assert "'titre'" in problems and "hors de l'intervalle ]0, 100]" in problems
    assert "note" in problems and "en double" in problems


def test_validation_strict_raises():
    with pytest.raises(ValueError):
        validation.validate_books(valid_books(), expected_rows=10, strict=True)


# ------------------------------------------------------------------ export
def test_save_dataset_writes_csv_parquet_and_sqlite(tmp_path):
    df = valid_books()
    paths = storage.save_dataset(df, "livres", tmp_path)
    assert {p.suffix for p in paths} == {".csv", ".parquet", ".sqlite"}
    assert len(pd.read_csv(tmp_path / "livres.csv")) == 3
    assert len(pd.read_parquet(tmp_path / "livres.parquet")) == 3
    with sqlite3.connect(tmp_path / "livres.sqlite") as connection:
        assert connection.execute("SELECT COUNT(*) FROM livres").fetchone()[0] == 3
    connection.close()


def test_save_dataset_rejects_unknown_format(tmp_path):
    with pytest.raises(ValueError):
        storage.save_dataset(valid_books(), "x", tmp_path, formats=("xml",))
