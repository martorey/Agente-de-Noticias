from __future__ import annotations

from datetime import timezone

import pytest
import requests
from conftest import EMPTY_FEED, RSS_FIXTURE

from agente.fetcher import fetch_all, fetch_source
from agente.sources import Source


class FakeResponse:
    def __init__(self, body: str = "", status: int = 200):
        self.content = body.encode("utf-8")
        self.text = body
        self.status_code = status

    @property
    def ok(self) -> bool:
        return self.status_code < 400

    def raise_for_status(self):
        if not self.ok:
            raise requests.HTTPError(f"HTTP {self.status_code}")


class FakeSession:
    """Session que responde según un mapa url -> respuesta (o excepción)."""

    def __init__(self, responses: dict):
        self.responses = responses
        self.calls: list[str] = []

    def get(self, url, **kwargs):
        self.calls.append(url)
        result = self.responses.get(url)
        if result is None:
            raise requests.ConnectionError("host no configurado en el test")
        if isinstance(result, Exception):
            raise result
        return result

    def close(self):
        pass


@pytest.fixture
def source() -> Source:
    return Source(
        name="Medio Test",
        section="nacional",
        urls=("https://a.cl/rss", "https://b.cl/rss"),
    )


class TestFetchSource:
    def test_parsea_feed_valido(self, source, config):
        session = FakeSession({"https://a.cl/rss": FakeResponse(RSS_FIXTURE)})
        articles, result = fetch_source(source, config, session)

        assert result.ok
        assert result.url_used == "https://a.cl/rss"
        # La tercera entrada del fixture no tiene título: se descarta.
        assert len(articles) == 2
        assert articles[0].title == "Gobierno anuncia plan de vivienda & empleo"
        assert articles[0].source == "Medio Test"
        assert articles[0].section == "nacional"

    def test_limpia_html_del_resumen(self, source, config):
        session = FakeSession({"https://a.cl/rss": FakeResponse(RSS_FIXTURE)})
        articles, _ = fetch_source(source, config, session)
        assert articles[0].summary == "El anuncio se realizó esta mañana."

    def test_extrae_fecha_en_utc(self, source, config):
        session = FakeSession({"https://a.cl/rss": FakeResponse(RSS_FIXTURE)})
        articles, _ = fetch_source(source, config, session)
        published = articles[0].published
        assert published is not None
        assert published.tzinfo is not None
        assert published.astimezone(timezone.utc).hour == 17

    def test_extrae_imagen_de_media_content(self, source, config):
        session = FakeSession({"https://a.cl/rss": FakeResponse(RSS_FIXTURE)})
        articles, _ = fetch_source(source, config, session)
        assert articles[0].image == "https://ejemplo.cl/foto.jpg"

    def test_usa_url_alternativa_si_la_primera_falla(self, source, config):
        session = FakeSession(
            {
                "https://a.cl/rss": requests.ConnectionError("caído"),
                "https://b.cl/rss": FakeResponse(RSS_FIXTURE),
            }
        )
        articles, result = fetch_source(source, config, session)
        assert result.ok
        assert result.url_used == "https://b.cl/rss"
        assert len(articles) == 2
        assert session.calls == ["https://a.cl/rss", "https://b.cl/rss"]

    def test_url_alternativa_ante_feed_vacio(self, source, config):
        session = FakeSession(
            {
                "https://a.cl/rss": FakeResponse(EMPTY_FEED),
                "https://b.cl/rss": FakeResponse(RSS_FIXTURE),
            }
        )
        _, result = fetch_source(source, config, session)
        assert result.ok
        assert result.url_used == "https://b.cl/rss"

    def test_url_alternativa_ante_http_error(self, source, config):
        session = FakeSession(
            {
                "https://a.cl/rss": FakeResponse("nope", status=404),
                "https://b.cl/rss": FakeResponse(RSS_FIXTURE),
            }
        )
        _, result = fetch_source(source, config, session)
        assert result.ok
        assert result.url_used == "https://b.cl/rss"

    def test_reporta_fallo_si_todas_fallan(self, source, config):
        session = FakeSession(
            {
                "https://a.cl/rss": requests.ConnectionError("caído"),
                "https://b.cl/rss": FakeResponse("", status=500),
            }
        )
        articles, result = fetch_source(source, config, session)
        assert articles == []
        assert not result.ok
        assert result.error

    def test_xml_corrupto_no_propaga_excepcion(self, source, config):
        session = FakeSession({"https://a.cl/rss": FakeResponse("<rss><no cerrado")})
        articles, result = fetch_source(source, config, session)
        assert articles == []
        assert not result.ok

    def test_respeta_max_items(self, config):
        limitada = Source(
            name="Limitada", section="nacional", urls=("https://a.cl/rss",), max_items=1
        )
        session = FakeSession({"https://a.cl/rss": FakeResponse(RSS_FIXTURE)})
        articles, _ = fetch_source(limitada, config, session)
        assert len(articles) == 1


class TestFetchAll:
    def test_una_fuente_caida_no_tumba_al_resto(self, config, monkeypatch):
        buena = Source(name="Buena", section="nacional", urls=("https://ok.cl/rss",))
        mala = Source(name="Mala", section="nacional", urls=("https://mal.cl/rss",))

        def fake_get(self, url, **kwargs):
            if "ok.cl" in url:
                return FakeResponse(RSS_FIXTURE)
            raise requests.ConnectionError("caído")

        monkeypatch.setattr(requests.Session, "get", fake_get)

        articles, results = fetch_all([buena, mala], config)
        assert len(articles) == 2
        assert {r.source_name: r.ok for r in results} == {"Buena": True, "Mala": False}

    def test_lista_vacia(self, config):
        articles, results = fetch_all([], config)
        assert articles == []
        assert results == []
