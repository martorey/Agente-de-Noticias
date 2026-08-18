"""Lectura de NOTIFY_MIN_NEW desde el entorno.

No hay tests de Config.from_env() en el resto del proyecto: los demás usan
el dataclass directo con dataclasses.replace(), que nunca pasa por el parseo
de variables de entorno. Como NOTIFY_MIN_NEW llega desde el workflow real de
Actions, este es el único punto que ejercita esa conexión.
"""

from __future__ import annotations

from agente.config import Config


def test_notify_min_new_default_es_uno(monkeypatch):
    monkeypatch.delenv("NOTIFY_MIN_NEW", raising=False)
    assert Config.from_env().notify_min_new == 1


def test_notify_min_new_toma_el_valor_del_entorno(monkeypatch):
    monkeypatch.setenv("NOTIFY_MIN_NEW", "10")
    assert Config.from_env().notify_min_new == 10


def test_notify_min_new_invalido_cae_al_default(monkeypatch):
    monkeypatch.setenv("NOTIFY_MIN_NEW", "no-es-un-numero")
    assert Config.from_env().notify_min_new == 1
