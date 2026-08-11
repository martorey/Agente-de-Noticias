from __future__ import annotations

import dataclasses

import pytest
import requests
from conftest import make_article

from agente import notifier
from agente.notifier import build_message, page_url, send_whatsapp


@pytest.fixture
def grouped():
    return {
        "nacional": [
            make_article("Congreso aprueba la reforma previsional tras meses de debate"),
            make_article("Alza del dólar preocupa a exportadores frutícolas", source="T13"),
            make_article("Metro extiende la línea 3 hacia Quilicura", source="La Tercera"),
            make_article("Cuarta noticia nacional que no debería aparecer"),
        ],
        "internacional": [
            make_article(
                "Unión Europea aprueba nuevo paquete de sanciones",
                section="internacional",
                source="BBC Mundo",
            ),
        ],
    }


class TestBuildMessage:
    def test_incluye_titulo_y_enlace(self, grouped, config, now):
        msg = build_message(grouped, config, "https://ejemplo.cl/?act=1", now)
        assert "Últimas noticias" in msg
        assert "https://ejemplo.cl/?act=1" in msg

    def test_incluye_encabezados_de_seccion(self, grouped, config, now):
        msg = build_message(grouped, config, "https://ejemplo.cl/", now)
        assert "*Chile*" in msg
        assert "*Internacional*" in msg

    def test_respeta_notify_headlines(self, grouped, config, now):
        cfg = dataclasses.replace(config, notify_headlines=2)
        msg = build_message(grouped, cfg, "https://ejemplo.cl/", now)
        assert msg.count("• ") == 3  # 2 nacionales + 1 internacional
        assert "Cuarta noticia nacional" not in msg

    def test_muestra_conteo_de_nuevas(self, grouped, config, now):
        msg = build_message(grouped, config, "https://ejemplo.cl/", now, new_count=4)
        assert "4 nuevos" in msg

    def test_sin_novedades(self, grouped, config, now):
        msg = build_message(grouped, config, "https://ejemplo.cl/", now, new_count=0)
        assert "sin novedades" in msg

    def test_omite_secciones_vacias(self, config, now):
        msg = build_message({"nacional": [make_article("Sólo nacional hoy")]}, config, "", now)
        assert "*Internacional*" not in msg

    def test_recorta_mensajes_largos_conservando_enlace(self, config, now):
        enorme = {
            "nacional": [
                make_article(f"Titular kilométrico número {i} " + "palabra " * 30)
                for i in range(40)
            ]
        }
        cfg = dataclasses.replace(config, notify_headlines=40)
        url = "https://ejemplo.cl/?act=202608111800"
        msg = build_message(enorme, cfg, url, now)
        assert len(msg) <= notifier.MAX_MESSAGE_CHARS
        assert msg.endswith(url)

    def test_hora_en_zona_local(self, grouped, config, now):
        # now es 18:00 UTC; Santiago está 4 horas atrás en agosto.
        msg = build_message(grouped, config, "", now)
        assert "14:00" in msg


class TestPageUrl:
    def test_agrega_parametro_anticache(self, config, now):
        url = page_url(config, now)
        assert url.startswith("https://martorey.github.io/Agente-de-Noticias/")
        assert "act=202608111800" in url

    def test_conserva_query_existente(self, config, now):
        cfg = dataclasses.replace(config, site_url="https://ejemplo.cl/pag?x=1")
        url = page_url(cfg, now)
        assert "x=1" in url and "act=" in url

    def test_sin_site_url_devuelve_vacio(self, config, now):
        cfg = dataclasses.replace(config, site_url="")
        assert page_url(cfg, now) == ""


class TestSendWhatsapp:
    def test_dry_run_no_envia(self, config):
        result = send_whatsapp("hola", config)
        assert not result.sent
        assert result.reason == "dry_run"

    def test_sin_credenciales_no_envia(self, config):
        cfg = dataclasses.replace(config, dry_run=False, whatsapp_apikey="")
        result = send_whatsapp("hola", cfg)
        assert not result.sent
        assert result.reason == "sin_credenciales"

    def test_envio_exitoso(self, config, monkeypatch):
        cfg = dataclasses.replace(config, dry_run=False)
        capturado = {}

        class Resp:
            status_code = 200
            text = "Message queued"
            ok = True

        def fake_get(url, **kwargs):
            capturado["url"] = url
            return Resp()

        monkeypatch.setattr(requests, "get", fake_get)
        result = send_whatsapp("hola mundo", cfg)

        assert result.sent
        assert "api.callmebot.com" in capturado["url"]
        assert "text=hola%20mundo" in capturado["url"]
        assert "apikey=123456" in capturado["url"]

    def test_codifica_caracteres_especiales(self, config, monkeypatch):
        cfg = dataclasses.replace(config, dry_run=False)
        capturado = {}

        class Resp:
            status_code = 200
            text = "ok"
            ok = True

        monkeypatch.setattr(
            requests, "get", lambda url, **kw: (capturado.setdefault("url", url), Resp())[1]
        )
        send_whatsapp("Ñandú & café\nlínea 2", cfg)

        url = capturado["url"]
        assert "&" not in url.split("text=")[1].split("&apikey")[0].replace("%26", "")
        assert "%0A" in url  # el salto de línea va escapado

    def test_no_filtra_credenciales_al_log(self, config, monkeypatch, caplog):
        """El error de requests trae la URL completa, con apikey y teléfono."""
        cfg = dataclasses.replace(config, dry_run=False)

        def fake_get(url, **kwargs):
            # Reproduce el mensaje real de requests, que incluye la URL.
            raise requests.ConnectionError(
                f"HTTPSConnectionPool(host='api.callmebot.com', port=443): "
                f"Max retries exceeded with url: {url.split('callmebot.com')[1]}"
            )

        monkeypatch.setattr(requests, "get", fake_get)
        monkeypatch.setattr(notifier.time, "sleep", lambda s: None)

        with caplog.at_level("WARNING"):
            result = send_whatsapp("hola", cfg, retries=2)

        registrado = caplog.text + result.reason
        assert "123456" not in registrado  # apikey
        assert "56900000000" not in registrado  # teléfono, con o sin +
        assert "%2B56900000000" not in registrado  # y su forma percent-encoded
        assert "***" in result.reason

    def test_reintenta_y_falla(self, config, monkeypatch):
        cfg = dataclasses.replace(config, dry_run=False)
        intentos = {"n": 0}

        def fake_get(url, **kwargs):
            intentos["n"] += 1
            raise requests.ConnectionError("sin red")

        monkeypatch.setattr(requests, "get", fake_get)
        monkeypatch.setattr(notifier.time, "sleep", lambda s: None)

        result = send_whatsapp("hola", cfg, retries=3)
        assert not result.sent
        assert intentos["n"] == 3

    def test_reintenta_y_lo_logra(self, config, monkeypatch):
        cfg = dataclasses.replace(config, dry_run=False)
        intentos = {"n": 0}

        class Resp:
            def __init__(self, code):
                self.status_code = code
                self.text = ""
                self.ok = code < 400

        def fake_get(url, **kwargs):
            intentos["n"] += 1
            return Resp(500 if intentos["n"] == 1 else 200)

        monkeypatch.setattr(requests, "get", fake_get)
        monkeypatch.setattr(notifier.time, "sleep", lambda s: None)

        result = send_whatsapp("hola", cfg, retries=3)
        assert result.sent
        assert intentos["n"] == 2
