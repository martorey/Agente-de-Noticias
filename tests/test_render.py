from __future__ import annotations

import json
from pathlib import Path

import pytest
from conftest import make_article

from agente.models import FeedResult
from agente.render import render_page, write_site


@pytest.fixture
def grouped():
    destacada = make_article("Congreso aprueba la reforma previsional")
    destacada.also_in = ["T13", "La Tercera"]
    return {
        "nacional": [
            destacada,
            make_article("Alza del dólar preocupa a exportadores", source="T13"),
        ],
        "internacional": [
            make_article(
                "Unión Europea aprueba sanciones",
                section="internacional",
                source="BBC Mundo",
                summary="El acuerdo se cerró tras dos días de negociación.",
            )
        ],
    }


@pytest.fixture
def results():
    return [
        FeedResult("Emol", "nacional", ok=True, article_count=12, url_used="https://emol.cl/rss"),
        FeedResult("T13", "nacional", ok=False, error="ConnectionError: caído"),
    ]


class TestRenderPage:
    def test_html_bien_formado(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert html.startswith("<!DOCTYPE html>")
        assert html.rstrip().endswith("</html>")
        assert '<html lang="es">' in html

    def test_incluye_titulares_y_enlaces(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        for article in grouped["nacional"] + grouped["internacional"]:
            assert article.title in html
            assert f'href="{article.link}"' in html

    def test_enlaces_abren_en_pestana_nueva_de_forma_segura(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert 'target="_blank" rel="noopener noreferrer"' in html

    def test_secciones_con_etiquetas_en_espanol(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert 'id="nacional"' in html and ">Chile</h2>" in html
        assert 'id="internacional"' in html and ">Internacional</h2>" in html

    def test_muestra_corroboracion(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert "3 medios" in html
        assert "También en La Tercera, T13" in html

    def test_reporte_de_salud_de_fuentes(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert "1 de 2 respondieron" in html
        assert "ConnectionError: caído" in html

    def test_escapa_html_malicioso(self, results, config, now):
        peligrosa = make_article(
            '<script>alert("xss")</script>',
            link='https://x.cl/a"onmouseover="alert(1)',
        )
        peligrosa.summary = "<img src=x onerror=alert(1)>"
        html = render_page({"nacional": [peligrosa]}, results, config, now)

        assert "<script>alert" not in html
        assert "&lt;script&gt;" in html
        assert 'onmouseover="alert(1)"' not in html
        assert "<img src=x" not in html

    @pytest.mark.parametrize(
        "enlace",
        [
            "javascript:alert(1)",
            "JavaScript:alert(1)",
            "  javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
            "vbscript:msgbox(1)",
        ],
    )
    def test_neutraliza_esquemas_peligrosos(self, results, config, now, enlace):
        # Escapar el HTML no basta: un href javascript: se ejecuta igual al clic.
        maliciosa = make_article("Titular aparentemente normal", link=enlace)
        html = render_page({"nacional": [maliciosa]}, results, config, now)

        assert 'href="#"' in html
        assert "javascript:" not in html.lower()
        assert "data:text/html" not in html

    def test_conserva_enlaces_legitimos(self, results, config, now):
        buena = make_article("Titular normal", link="https://emol.cl/nota?id=7")
        html = render_page({"nacional": [buena]}, results, config, now)
        assert 'href="https://emol.cl/nota?id=7"' in html

    def test_seccion_vacia_muestra_aviso(self, results, config, now):
        html = render_page({"nacional": []}, results, config, now)
        assert "No se pudieron recuperar noticias" in html

    def test_hora_local_en_encabezado(self, grouped, results, config, now):
        html = render_page(grouped, results, config, now)
        assert "14:00" in html  # 18:00 UTC en horario de Santiago
        assert "martes 11 de agosto" in html

    def test_noticia_sin_fecha_no_rompe(self, results, config, now):
        sin_fecha = make_article("Noticia sin fecha de publicación", minutes_ago=None)
        html = render_page({"nacional": [sin_fecha]}, results, config, now)
        assert "Noticia sin fecha de publicación" in html


class TestWriteSite:
    def test_escribe_archivos(self, grouped, results, config, now):
        index = write_site(grouped, results, config, now)
        out = Path(config.output_dir)

        assert index.exists()
        assert (out / "feed.json").exists()
        assert (out / ".nojekyll").exists()

    def test_feed_json_valido(self, grouped, results, config, now):
        write_site(grouped, results, config, now)
        data = json.loads((Path(config.output_dir) / "feed.json").read_text("utf-8"))

        assert data["total"] == 3
        assert len(data["secciones"]["nacional"]) == 2
        assert data["secciones"]["nacional"][0]["fuente"] == "Emol"
        assert data["fuentes"][1]["ok"] is False

    def test_crea_directorio_si_no_existe(self, grouped, results, config, now):
        assert not Path(config.output_dir).exists()
        write_site(grouped, results, config, now)
        assert Path(config.output_dir).is_dir()
