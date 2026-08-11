"""Titulares de agregadores: separar "Titular - Medio"."""

from __future__ import annotations

import pytest

from agente.fetcher import _entry_to_article
from agente.processing import split_aggregator_title
from agente.sources import Source

AGREGADOR = Source(
    name="Google News Chile",
    section="nacional",
    urls=("https://news.google.com/rss",),
    aggregator=True,
)
DIRECTO = Source(
    name="La Tercera", section="nacional", urls=("https://latercera.com/feed",)
)


class TestSplit:
    @pytest.mark.parametrize(
        "titulo,esperado_titular,esperado_medio",
        [
            (
                "Congreso aprueba la reforma previsional tras meses - Emol",
                "Congreso aprueba la reforma previsional tras meses",
                "Emol",
            ),
            (
                "Alza del dólar golpea a los exportadores frutícolas - La Tercera",
                "Alza del dólar golpea a los exportadores frutícolas",
                "La Tercera",
            ),
            (
                "Metro extiende la línea 3 hacia Quilicura - BioBioChile",
                "Metro extiende la línea 3 hacia Quilicura",
                "BioBioChile",
            ),
        ],
    )
    def test_separa_medio(self, titulo, esperado_titular, esperado_medio):
        assert split_aggregator_title(titulo) == (esperado_titular, esperado_medio)

    @pytest.mark.parametrize(
        "titulo",
        [
            # Sin sufijo de medio.
            "Congreso aprueba la reforma previsional tras meses de debate",
            # El sufijo es parte de la frase, no un medio.
            "El acuerdo llegó tarde - y con menos apoyo del que esperaban todos.",
            # Sufijo demasiado largo para ser un nombre de medio.
            "Gobierno anuncia medidas - un paquete de ayudas para las regiones",
            # Titular restante demasiado corto: probablemente no era un sufijo.
            "Chile - Argentina",
        ],
    )
    def test_no_mutila_titulares_legitimos(self, titulo):
        titular, medio = split_aggregator_title(titulo)
        assert titular == titulo.strip()
        assert medio == ""

    def test_usa_el_ultimo_guion(self):
        titular, medio = split_aggregator_title(
            "Caso Convenios - Fundaciones: nuevas aristas del sumario - Ex-Ante"
        )
        assert medio == "Ex-Ante"
        assert titular.startswith("Caso Convenios - Fundaciones")


class _Entry(dict):
    """feedparser entrega objetos tipo dict."""


class TestEnArticulo:
    def _entry(self, titulo):
        return _Entry(title=titulo, link="https://medio.cl/nota", summary="")

    def test_agregador_atribuye_al_medio_real(self):
        art = _entry_to_article(
            self._entry("Congreso aprueba la reforma previsional - Emol"), AGREGADOR
        )
        assert art.source == "Emol"
        assert art.title == "Congreso aprueba la reforma previsional"
        assert art.section == "nacional"

    def test_agregador_sin_sufijo_conserva_su_nombre(self):
        art = _entry_to_article(
            self._entry("Un titular sin ningún sufijo de medio aquí"), AGREGADOR
        )
        assert art.source == "Google News Chile"

    def test_fuente_directa_no_se_toca(self):
        art = _entry_to_article(
            self._entry("Alza del dólar golpea a exportadores - La Tercera"), DIRECTO
        )
        assert art.source == "La Tercera"
        # El titular queda intacto: no es un agregador.
        assert art.title.endswith("- La Tercera")

    def test_permite_deduplicar_contra_el_feed_directo(self):
        """La misma nota por el agregador y por el medio debe agruparse."""
        from agente.processing import deduplicate

        via_agregador = _entry_to_article(
            _Entry(
                title="Congreso aprueba la reforma previsional tras meses - La Tercera",
                link="https://news.google.com/rss/articles/xyz",
                summary="",
            ),
            AGREGADOR,
        )
        via_directo = _entry_to_article(
            _Entry(
                title="Congreso aprueba la reforma previsional tras meses",
                link="https://www.latercera.com/nota",
                summary="",
            ),
            DIRECTO,
        )
        assert len(deduplicate([via_agregador, via_directo])) == 1
