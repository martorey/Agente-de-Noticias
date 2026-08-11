from __future__ import annotations

from conftest import make_article

from agente.processing import (
    canonical_url,
    clean_text,
    deduplicate,
    drop_stale,
    prepare,
    rank,
    title_tokens,
)


class TestCleanText:
    def test_quita_html_y_entidades(self):
        assert clean_text("<p>Hola &amp; chao</p>") == "Hola & chao"

    def test_normaliza_espacios(self):
        assert clean_text("  uno\n\n  dos\t tres ") == "uno dos tres"

    def test_vacio(self):
        assert clean_text("") == ""


class TestCanonicalUrl:
    def test_quita_tracking(self):
        url = "https://www.emol.com/nota?utm_source=rss&utm_medium=feed&id=7"
        assert canonical_url(url) == "https://emol.com/nota?id=7"

    def test_quita_fragmento_y_barra_final(self):
        assert canonical_url("https://t13.cl/nota/#comentarios") == "https://t13.cl/nota"

    def test_http_y_https_convergen(self):
        assert canonical_url("http://www.t13.cl/x") == canonical_url("https://t13.cl/x/")

    def test_quita_fbclid(self):
        assert canonical_url("https://a.cl/n?fbclid=abc") == "https://a.cl/n"


class TestTitleTokens:
    def test_ignora_acentos_y_stopwords(self):
        assert title_tokens("El Gobierno de Chile anunció") == frozenset(
            {"gobierno", "chile", "anuncio"}
        )

    def test_descarta_palabras_cortas(self):
        assert "de" not in title_tokens("Ministro de Hacienda")


class TestDeduplicate:
    def test_agrupa_por_enlace_canonico(self):
        a = make_article("Titular A", link="https://x.cl/n?utm_source=rss")
        b = make_article("Titular A distinto texto", source="T13", link="https://www.x.cl/n/")
        result = deduplicate([a, b])
        assert len(result) == 1
        assert result[0].also_in == ["T13"]

    def test_agrupa_titulares_parecidos(self):
        a = make_article("Gobierno anuncia plan de vivienda para familias vulnerables")
        b = make_article(
            "Gobierno anuncia un plan de vivienda para las familias vulnerables",
            source="La Tercera",
        )
        result = deduplicate([a, b])
        assert len(result) == 1
        assert result[0].corroboration == 2

    def test_no_agrupa_historias_distintas(self):
        a = make_article("Gobierno anuncia plan de vivienda")
        b = make_article("Alza del dólar preocupa a exportadores", source="T13")
        assert len(deduplicate([a, b])) == 2

    def test_conserva_el_mejor_resumen(self):
        corto = make_article("Misma noticia importante hoy", summary="Corto")
        largo = make_article(
            "Misma noticia importante hoy",
            source="T13",
            link="https://otro.cl/n",
            summary="Un resumen bastante más completo de la misma historia.",
        )
        result = deduplicate([corto, largo])
        assert result[0].summary.startswith("Un resumen bastante")

    def test_misma_fuente_no_se_autolista(self):
        a = make_article("Noticia repetida en el feed")
        b = make_article("Noticia repetida en el feed", link="https://otro.cl/z")
        result = deduplicate([a, b])
        assert result[0].also_in == []


class TestDropStale:
    def test_descarta_viejas(self, now):
        vieja = make_article("Vieja", minutes_ago=60 * 40)
        nueva = make_article("Nueva", minutes_ago=30)
        result = drop_stale([vieja, nueva], max_age_hours=24, now=now)
        assert [a.title for a in result] == ["Nueva"]

    def test_conserva_sin_fecha(self, now):
        sin_fecha = make_article("Sin fecha", minutes_ago=None)
        assert drop_stale([sin_fecha], 24, now) == [sin_fecha]

    def test_cero_desactiva_filtro(self, now):
        vieja = make_article("Vieja", minutes_ago=60 * 100)
        assert drop_stale([vieja], 0, now) == [vieja]


class TestRank:
    def test_prioriza_recientes(self, now):
        vieja = make_article("Vieja", minutes_ago=600)
        nueva = make_article("Nueva", minutes_ago=5)
        assert rank([vieja, nueva], now)[0].title == "Nueva"

    def test_corroboracion_desempata(self, now):
        sola = make_article("Sola", minutes_ago=20)
        cubierta = make_article("Cubierta", minutes_ago=25)
        cubierta.also_in = ["T13", "La Tercera", "Cooperativa"]
        assert rank([sola, cubierta], now)[0].title == "Cubierta"


class TestPrepare:
    def test_agrupa_por_seccion_y_limita(self, now):
        nacionales = [
            "Congreso aprueba reforma previsional tras larga tramitación",
            "Alza sostenida del dólar preocupa a los exportadores frutícolas",
            "Metro de Santiago extiende la línea 3 hacia Quilicura",
            "Sernapesca detecta escape masivo de salmones en Chiloé",
            "Corte Suprema confirma fallo sobre isapres y cobros en exceso",
            "Ministerio de Salud reporta baja en contagios respiratorios",
            "Estudiantes marchan por el centro de Valparaíso este martes",
        ]
        internacionales = [
            "Unión Europea aprueba nuevo paquete de sanciones económicas",
            "Terremoto de magnitud siete sacude la costa de Indonesia",
            "Cumbre climática cierra sin acuerdo sobre combustibles fósiles",
        ]
        articles = [
            make_article(t, minutes_ago=i) for i, t in enumerate(nacionales, start=1)
        ] + [
            make_article(
                t, section="internacional", source="BBC Mundo", minutes_ago=i
            )
            for i, t in enumerate(internacionales, start=1)
        ]
        grouped = prepare(articles, max_age_hours=24, max_per_section=5, now=now)
        assert len(grouped["nacional"]) == 5
        assert len(grouped["internacional"]) == 3

    def test_titulares_cortos_no_se_fusionan(self):
        a = make_article("Alza del dólar")
        b = make_article("Alza del cobre", source="T13")
        assert len(deduplicate([a, b])) == 2

    def test_sin_noticias_devuelve_vacio(self, now):
        assert prepare([], 24, 10, now) == {}
