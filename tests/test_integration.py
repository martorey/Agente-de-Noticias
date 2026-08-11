"""Prueba de extremo a extremo con un servidor HTTP local.

Ejercita el camino real de red (requests + feedparser) sin depender de
internet, y verifica que una corrida completa publique la página y componga
el mensaje de WhatsApp.
"""

from __future__ import annotations

import dataclasses
import http.server
import json
import threading
from pathlib import Path

import pytest

from agente import main as main_mod
from agente.fetcher import fetch_all
from agente.notifier import NotifyResult
from agente.sources import Source

FEED_NACIONAL = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Nacional</title>
  <item><title>Congreso aprueba la reforma previsional tras meses de debate</title>
    <link>https://medio.cl/reforma</link>
    <description>La votación terminó pasada la medianoche.</description></item>
  <item><title>Alza del dólar preocupa a los exportadores frutícolas</title>
    <link>https://medio.cl/dolar</link>
    <description>El tipo de cambio superó un nuevo máximo.</description></item>
</channel></rss>
"""

FEED_NACIONAL_2 = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Otro medio</title>
  <item><title>El Congreso aprueba la reforma previsional luego de meses de debate</title>
    <link>https://otro.cl/reforma-previsional</link>
    <description>Cobertura del mismo hecho por otro medio.</description></item>
  <item><title>Metro de Santiago extiende la línea 3 hacia Quilicura</title>
    <link>https://otro.cl/metro</link>
    <description>Las obras comenzarán el próximo año.</description></item>
</channel></rss>
"""

FEED_INTERNACIONAL = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Internacional</title>
  <item><title>Unión Europea aprueba un nuevo paquete de sanciones</title>
    <link>https://mundo.com/sanciones</link>
    <description>El acuerdo se cerró tras dos días de negociación.</description></item>
</channel></rss>
"""

ROUTES = {
    "/nacional.xml": FEED_NACIONAL,
    "/nacional2.xml": FEED_NACIONAL_2,
    "/internacional.xml": FEED_INTERNACIONAL,
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        body = ROUTES.get(self.path)
        if body is None:
            self.send_error(404)
            return
        payload = body.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/rss+xml; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):  # silencia el log del servidor
        pass


@pytest.fixture(scope="module")
def server():
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


@pytest.fixture
def sources(server):
    return [
        Source(name="Medio Uno", section="nacional", urls=(f"{server}/nacional.xml",)),
        Source(name="Medio Dos", section="nacional", urls=(f"{server}/nacional2.xml",)),
        Source(
            name="Mundo",
            section="internacional",
            urls=(f"{server}/no-existe.xml", f"{server}/internacional.xml"),
        ),
        Source(name="Caído", section="nacional", urls=(f"{server}/roto.xml",)),
    ]


def test_fetch_real_por_http(sources, config):
    articles, results = fetch_all(sources, config)

    assert len(articles) == 5
    ok = {r.source_name: r.ok for r in results}
    assert ok == {"Medio Uno": True, "Medio Dos": True, "Mundo": True, "Caído": False}

    # "Mundo" tuvo que caer al segundo URL de su lista.
    mundo = next(r for r in results if r.source_name == "Mundo")
    assert mundo.url_used.endswith("/internacional.xml")


def _capturar_envios(monkeypatch, destino: list) -> None:
    """Reemplaza el envío real por uno que sólo registra el mensaje."""

    def fake_send(message, cfg, **kwargs):
        destino.append(message)
        return NotifyResult(sent=True, reason="ok", message=message, status_code=200)

    monkeypatch.setattr(main_mod, "send_whatsapp", fake_send)


def test_corrida_completa(sources, config, monkeypatch):
    monkeypatch.setattr(main_mod, "active_sources", lambda *a, **k: sources)
    enviados: list[str] = []
    _capturar_envios(monkeypatch, enviados)

    codigo = main_mod.run(config)
    assert codigo == 0

    index = Path(config.output_dir) / "index.html"
    html = index.read_text("utf-8")

    # La misma historia cubierta por dos medios queda una sola vez, corroborada.
    assert html.count("reforma previsional") >= 1
    assert "También en Medio Dos" in html or "También en Medio Uno" in html
    assert "Unión Europea aprueba un nuevo paquete de sanciones" in html
    assert "3 de 4 respondieron" in html

    data = json.loads((Path(config.output_dir) / "feed.json").read_text("utf-8"))
    assert data["total"] == 4  # 5 crudas - 1 duplicada
    assert len(data["secciones"]["internacional"]) == 1

    # El mensaje de WhatsApp se compuso con el enlace a la página.
    assert enviados and "martorey.github.io" in enviados[0]


def test_estado_marca_novedades_en_la_segunda_corrida(sources, config, monkeypatch):
    # Con notify_mode=siempre el segundo aviso sale igual, informando que no
    # hubo novedades; es lo que hace visible el conteo.
    cfg = dataclasses.replace(config, notify_mode="siempre")
    monkeypatch.setattr(main_mod, "active_sources", lambda *a, **k: sources)
    mensajes: list[str] = []
    _capturar_envios(monkeypatch, mensajes)

    main_mod.run(cfg)
    assert "4 nuevos" in mensajes[0]

    main_mod.run(cfg)
    assert "sin novedades" in mensajes[1]


def test_modo_solo_nuevas_omite_el_envio(sources, config, monkeypatch):
    cfg = dataclasses.replace(config, notify_mode="solo-nuevas")
    monkeypatch.setattr(main_mod, "active_sources", lambda *a, **k: sources)
    mensajes: list[str] = []
    _capturar_envios(monkeypatch, mensajes)

    main_mod.run(cfg)
    assert len(mensajes) == 1

    main_mod.run(cfg)  # nada nuevo: no debe volver a avisar
    assert len(mensajes) == 1


def test_sin_fuentes_vivas_no_publica(config, monkeypatch, server):
    rotas = [Source(name="Rota", section="nacional", urls=(f"{server}/roto.xml",))]
    monkeypatch.setattr(main_mod, "active_sources", lambda *a, **k: rotas)
    monkeypatch.setattr(
        main_mod, "send_whatsapp", lambda *a, **kw: pytest.fail("no debe avisar")
    )

    assert main_mod.run(config) == 1
    assert not (Path(config.output_dir) / "index.html").exists()


def test_check_feeds_reporta_estado(sources, config, monkeypatch, capsys):
    monkeypatch.setattr(main_mod, "active_sources", lambda *a, **k: sources)
    assert main_mod.check_feeds(config) == 0

    salida = capsys.readouterr().out
    assert "3/4 fuentes respondieron" in salida
    assert "✅ Medio Uno" in salida
    assert "❌ Caído" in salida
