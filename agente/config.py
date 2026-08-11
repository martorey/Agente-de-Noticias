"""Configuración leída desde variables de entorno."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

DEFAULT_TZ = "America/Santiago"


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "si", "sí", "on"}


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _env_set(name: str) -> frozenset[str]:
    raw = os.environ.get(name, "")
    return frozenset(part.strip() for part in raw.split(",") if part.strip())


@dataclass(frozen=True)
class Config:
    # --- Publicación ---
    site_url: str = ""
    site_title: str = "Últimas noticias"
    output_dir: str = "public"
    timezone: str = DEFAULT_TZ

    # --- Recolección ---
    max_items_per_section: int = 40
    max_age_hours: int = 24
    request_timeout: int = 20
    max_workers: int = 12
    extra_sources: frozenset[str] = field(default_factory=frozenset)
    excluded_sources: frozenset[str] = field(default_factory=frozenset)

    # --- WhatsApp (CallMeBot) ---
    whatsapp_phone: str = ""
    whatsapp_apikey: str = ""
    # "solo-nuevas" calla cuando no hay titulares nuevos respecto de la corrida
    # anterior; "siempre" envía en cada corrida.
    notify_mode: str = "solo-nuevas"
    notify_headlines: int = 3
    dry_run: bool = False

    # --- Estado ---
    state_file: str = ".estado/vistos.json"

    @property
    def tz(self) -> ZoneInfo:
        try:
            return ZoneInfo(self.timezone)
        except Exception:
            return ZoneInfo(DEFAULT_TZ)

    @property
    def whatsapp_configured(self) -> bool:
        return bool(self.whatsapp_phone and self.whatsapp_apikey)

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            site_url=os.environ.get("SITE_URL", "").strip().rstrip("/"),
            site_title=os.environ.get("SITE_TITLE", "Últimas noticias").strip()
            or "Últimas noticias",
            output_dir=os.environ.get("OUTPUT_DIR", "public").strip() or "public",
            timezone=os.environ.get("TIMEZONE", DEFAULT_TZ).strip() or DEFAULT_TZ,
            max_items_per_section=_env_int("MAX_ITEMS_PER_SECTION", 40),
            max_age_hours=_env_int("MAX_AGE_HOURS", 24),
            request_timeout=_env_int("REQUEST_TIMEOUT", 20),
            max_workers=_env_int("MAX_WORKERS", 12),
            extra_sources=_env_set("FUENTES_EXTRA"),
            excluded_sources=_env_set("FUENTES_EXCLUIDAS"),
            whatsapp_phone=os.environ.get("CALLMEBOT_PHONE", "").strip(),
            whatsapp_apikey=os.environ.get("CALLMEBOT_APIKEY", "").strip(),
            notify_mode=os.environ.get("NOTIFY_MODE", "solo-nuevas").strip().lower()
            or "solo-nuevas",
            notify_headlines=_env_int("NOTIFY_HEADLINES", 3),
            dry_run=_env_bool("DRY_RUN", False),
            state_file=os.environ.get("STATE_FILE", ".estado/vistos.json").strip()
            or ".estado/vistos.json",
        )
