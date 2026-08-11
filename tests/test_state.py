from __future__ import annotations

import json

from conftest import make_article

from agente.state import MAX_REMEMBERED, State, count_new, load, save


class TestLoad:
    def test_archivo_inexistente(self, tmp_path):
        estado = load(tmp_path / "no-existe.json")
        assert estado.seen == []
        assert estado.last_run is None

    def test_archivo_corrupto_no_rompe(self, tmp_path):
        archivo = tmp_path / "estado.json"
        archivo.write_text("{ esto no es json", encoding="utf-8")
        assert load(archivo).seen == []

    def test_lee_estado_valido(self, tmp_path):
        archivo = tmp_path / "estado.json"
        archivo.write_text(
            json.dumps({"vistos": ["a", "b"], "ultima_corrida": "2026-08-11T18:00:00Z"}),
            encoding="utf-8",
        )
        estado = load(archivo)
        assert estado.seen == ["a", "b"]
        assert estado.last_run == "2026-08-11T18:00:00Z"


class TestSave:
    def test_crea_directorios(self, tmp_path):
        destino = tmp_path / "sub" / "dir" / "estado.json"
        save(destino, [make_article("Una noticia cualquiera")], State())
        assert destino.exists()

    def test_conserva_historial_previo(self, tmp_path):
        archivo = tmp_path / "estado.json"
        articulo = make_article("Noticia fresca de hoy")
        save(archivo, [articulo], State(seen=["viejo1", "viejo2"]))

        data = json.loads(archivo.read_text("utf-8"))
        assert articulo.uid in data["vistos"]
        assert "viejo1" in data["vistos"]

    def test_recorta_historial(self, tmp_path):
        archivo = tmp_path / "estado.json"
        previo = State(seen=[f"id{i}" for i in range(MAX_REMEMBERED + 200)])
        save(archivo, [make_article("Noticia nueva de prueba")], previo)

        data = json.loads(archivo.read_text("utf-8"))
        assert len(data["vistos"]) == MAX_REMEMBERED

    def test_sin_duplicados(self, tmp_path):
        archivo = tmp_path / "estado.json"
        articulo = make_article("Noticia repetida en el estado")
        save(archivo, [articulo], State(seen=[articulo.uid]))

        data = json.loads(archivo.read_text("utf-8"))
        assert data["vistos"].count(articulo.uid) == 1


class TestCountNew:
    def test_todas_nuevas_sin_estado(self):
        articulos = [make_article("Primera noticia"), make_article("Segunda noticia")]
        assert count_new(articulos, State()) == 2

    def test_ignora_conocidas(self):
        vista = make_article("Noticia ya conocida por el agente")
        nueva = make_article("Noticia recién publicada ahora")
        assert count_new([vista, nueva], State(seen=[vista.uid])) == 1

    def test_ciclo_completo(self, tmp_path):
        archivo = tmp_path / "estado.json"
        primera = [make_article("Noticia de la primera corrida")]

        assert count_new(primera, load(archivo)) == 1
        save(archivo, primera, load(archivo))

        # Segunda corrida: la misma noticia ya no cuenta como nueva.
        assert count_new(primera, load(archivo)) == 0

        segunda = primera + [make_article("Noticia aparecida después")]
        assert count_new(segunda, load(archivo)) == 1


class TestNovedadIndependienteDelRepresentante:
    """La misma historia no debe parecer nueva si cambia el medio representante.

    Las fuentes se consultan en paralelo, así que entre corridas puede ganar
    la versión de otro medio.
    """

    def _historia_en_dos_medios(self):
        a = make_article(
            "Congreso aprueba la reforma previsional tras meses de debate",
            source="Emol",
            link="https://emol.cl/reforma",
        )
        b = make_article(
            "El Congreso aprueba la reforma previsional luego de meses de debate",
            source="T13",
            link="https://t13.cl/reforma-previsional",
        )
        return a, b

    def test_orden_invertido_no_genera_falsa_novedad(self, tmp_path):
        from agente.processing import deduplicate, stable_order

        archivo = tmp_path / "estado.json"
        a, b = self._historia_en_dos_medios()

        primera = deduplicate(stable_order([a, b]))
        assert len(primera) == 1
        assert count_new(primera, load(archivo)) == 1
        save(archivo, primera, load(archivo))

        # Segunda corrida: los feeds llegan en el orden opuesto.
        a2, b2 = self._historia_en_dos_medios()
        segunda = deduplicate(stable_order([b2, a2]))
        assert count_new(segunda, load(archivo)) == 0

    def test_se_guardan_los_uids_fusionados(self, tmp_path):
        from agente.processing import deduplicate

        archivo = tmp_path / "estado.json"
        a, b = self._historia_en_dos_medios()
        representante = deduplicate([a, b])[0]

        save(archivo, [representante], State())
        guardados = set(json.loads(archivo.read_text("utf-8"))["vistos"])
        assert a.uid in guardados and b.uid in guardados


class TestUid:
    def test_estable_entre_corridas(self):
        a = make_article("Misma noticia")
        b = make_article("Misma noticia")
        assert a.uid == b.uid

    def test_ignora_parametros_de_tracking(self):
        a = make_article("Noticia", link="https://x.cl/n?utm_source=rss")
        b = make_article("Noticia", link="https://www.x.cl/n/")
        assert a.uid == b.uid

    def test_distinto_por_fuente(self):
        a = make_article("Noticia igual", source="Emol", link="https://x.cl/n")
        b = make_article("Noticia igual", source="T13", link="https://x.cl/n")
        assert a.uid != b.uid
