"""Tests del descubrimiento de feeds, contra un servidor HTTP local."""

from __future__ import annotations

import http.server
import threading

import pytest

from agente.discover import USER_AGENTS, discover_source
from agente.sources import Source

FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Medio</title>
  <item><title>Un titular cualquiera</title><link>https://medio.cl/n1</link></item>
  <item><title>Otro titular más</title><link>https://medio.cl/n2</link></item>
</channel></rss>
"""

PORTADA = """<!DOCTYPE html><html><head>
<title>Portada</title>
<link rel="alternate" type="application/rss+xml" title="Feed" href="/declarado.xml">
</head><body>Hola</body></html>
"""

# El navegador es el primer User-Agent de la lista; "lector" es el segundo.
UA_NAVEGADOR = USER_AGENTS[0][1]
UA_LECTOR = USER_AGENTS[1][1]


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        ua = self.headers.get("User-Agent", "")
        ruta = self.path

        # /solo-navegador.xml responde 404 a cualquier cliente que no lo sea.
        if ruta == "/solo-navegador.xml" and ua != UA_NAVEGADOR:
            self.send_error(404)
            return
        # /solo-lector.xml sólo acepta el segundo User-Agent.
        if ruta == "/solo-lector.xml" and ua != UA_LECTOR:
            self.send_error(404)
            return

        cuerpo = {
            "/": PORTADA,
            "/declarado.xml": FEED,
            "/feed/": FEED,
            "/solo-navegador.xml": FEED,
            "/solo-lector.xml": FEED,
        }.get(ruta)

        if cuerpo is None:
            self.send_error(404)
            return
        payload = cuerpo.encode("utf-8")
        self.send_response(200)
        tipo = "text/html" if ruta == "/" else "application/rss+xml"
        self.send_header("Content-Type", f"{tipo}; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


@pytest.fixture(scope="module")
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def _source(server: str, urls: tuple[str, ...]) -> Source:
    return Source(name="Medio", section="nacional", urls=urls, homepage=server)


def test_encuentra_la_url_configurada(server):
    d = discover_source(_source(server, (f"{server}/declarado.xml",)))
    assert d.working
    assert d.working[0].entries == 2
    assert d.working[0].url.endswith("/declarado.xml")


def test_autodiscovery_desde_la_portada(server):
    # La URL configurada no existe: hay que leerla del <link> de la portada.
    d = discover_source(_source(server, (f"{server}/inexistente.xml",)))
    urls = [c.url for c in d.working]
    assert any(u.endswith("/declarado.xml") for u in urls)
    assert any("portada declara" in n for n in d.notes)


def test_cae_a_rutas_habituales(server):
    # Sin portada declarada no queda más que probar rutas conocidas.
    fuente = Source(
        name="Medio",
        section="nacional",
        urls=(f"{server}/inexistente.xml",),
        homepage=f"{server}/sin-portada",
    )
    d = discover_source(fuente)
    assert not d.working  # /sin-portada no existe, y las rutas cuelgan de él


def test_detecta_feed_que_exige_navegador(server):
    d = discover_source(_source(server, (f"{server}/solo-navegador.xml",)))
    assert d.working
    assert d.working[0].ua_label == "navegador"


def test_detecta_feed_que_exige_otro_cliente(server):
    """Si el navegador es rechazado, se prueba el siguiente User-Agent."""
    d = discover_source(_source(server, (f"{server}/solo-lector.xml",)))
    assert d.working
    assert d.working[0].ua_label == "lector"


def test_reporta_cuando_no_hay_nada(server):
    fuente = Source(
        name="Fantasma",
        section="nacional",
        urls=("http://127.0.0.1:9/nada.xml",),
        homepage="http://127.0.0.1:9",
    )
    d = discover_source(fuente)
    assert not d.working
    assert "sin feed detectado" in d.notes
