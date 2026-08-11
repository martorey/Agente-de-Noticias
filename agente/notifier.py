"""Envío del aviso por WhatsApp usando CallMeBot."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, quote, urlencode, urlsplit, urlunsplit

import requests

from .config import Config
from .models import Article

log = logging.getLogger(__name__)

CALLMEBOT_ENDPOINT = "https://api.callmebot.com/whatsapp.php"
# CallMeBot corta los mensajes largos; dejamos margen bajo su límite práctico.
MAX_MESSAGE_CHARS = 900


@dataclass
class NotifyResult:
    sent: bool
    reason: str = ""
    message: str = ""
    status_code: int | None = None


def _redact(text: str, config: Config) -> str:
    """Oculta credenciales antes de que lleguen al log.

    Las excepciones de requests incluyen la URL completa, que lleva la apikey y
    el teléfono. GitHub enmascara secretos sólo por coincidencia exacta, y en la
    URL viajan percent-encoded, así que el enmascarado automático no los
    reconocería.
    """
    for secret in (config.whatsapp_apikey, config.whatsapp_phone):
        if not secret:
            continue
        for variante in {secret, quote(secret, safe=""), quote(secret)}:
            if variante:
                text = text.replace(variante, "***")
    return text


def _shorten(text: str, limit: int) -> str:
    text = text.strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip(" ,;:.—-") + "…"


def build_message(
    grouped: dict[str, list[Article]],
    config: Config,
    url: str,
    generated_at: datetime | None = None,
    new_count: int | None = None,
) -> str:
    """Redacta el texto del WhatsApp: resumen corto y el link a la página."""
    generated_at = generated_at or datetime.now(timezone.utc)
    hora = generated_at.astimezone(config.tz).strftime("%H:%M")
    total = sum(len(items) for items in grouped.values())

    lines = [f"*📰 {config.site_title}* · {hora}"]

    resumen = f"{total} titulares"
    if new_count is not None:
        resumen += f" · {new_count} nuevos" if new_count else " · sin novedades"
    lines.append(resumen)

    from .render import SECTION_LABELS

    per_section = max(1, config.notify_headlines)
    for section in ("nacional", "internacional"):
        articles = grouped.get(section) or []
        if not articles:
            continue
        lines.append("")
        lines.append(f"*{SECTION_LABELS.get(section, section.capitalize())}*")
        for article in articles[:per_section]:
            lines.append(f"• {_shorten(article.title, 110)}")

    if url:
        lines.append("")
        lines.append(f"👉 {url}")

    message = "\n".join(lines)
    if len(message) > MAX_MESSAGE_CHARS:
        # Recortar por líneas conservando siempre el enlace final.
        tail = f"\n\n👉 {url}" if url else ""
        budget = MAX_MESSAGE_CHARS - len(tail)
        kept: list[str] = []
        used = 0
        for line in lines:
            if line.startswith("👉"):
                continue
            extra = len(line) + 1
            if used + extra > budget:
                break
            kept.append(line)
            used += extra
        message = "\n".join(kept).rstrip() + tail
    return message


def page_url(config: Config, generated_at: datetime | None = None) -> str:
    """URL pública con parámetro anti-caché.

    Sin esto WhatsApp reutiliza la vista previa del enlace y el mensaje de las
    18:30 muestra los titulares de las 18:00.
    """
    if not config.site_url:
        return ""
    generated_at = generated_at or datetime.now(timezone.utc)
    stamp = generated_at.strftime("%Y%m%d%H%M")

    parts = urlsplit(config.site_url)
    path = parts.path if parts.path.endswith("/") else parts.path + "/"
    query = parse_qsl(parts.query, keep_blank_values=True) + [("act", stamp)]
    return urlunsplit(
        (parts.scheme or "https", parts.netloc, path, urlencode(query), "")
    )


def send_whatsapp(
    message: str, config: Config, retries: int = 3
) -> NotifyResult:
    """Envía el mensaje por CallMeBot, con reintentos ante fallos transitorios."""
    if config.dry_run:
        log.info("DRY_RUN activo: no se envía WhatsApp.\n%s", message)
        return NotifyResult(sent=False, reason="dry_run", message=message)

    if not config.whatsapp_configured:
        log.warning(
            "Falta CALLMEBOT_PHONE o CALLMEBOT_APIKEY: se omite el aviso de WhatsApp."
        )
        return NotifyResult(sent=False, reason="sin_credenciales", message=message)

    params = {
        "phone": config.whatsapp_phone,
        "text": message,
        "apikey": config.whatsapp_apikey,
    }
    # CallMeBot es sensible al encoding: construimos la query a mano.
    query = "&".join(f"{k}={quote(str(v), safe='')}" for k, v in params.items())
    url = f"{CALLMEBOT_ENDPOINT}?{query}"

    last_error = ""
    last_status: int | None = None
    for attempt in range(1, retries + 1):
        try:
            response = requests.get(url, timeout=config.request_timeout)
            last_status = response.status_code
            body = (response.text or "").strip()
            if response.ok:
                log.info("WhatsApp enviado (HTTP %s).", response.status_code)
                return NotifyResult(
                    sent=True,
                    reason="ok",
                    message=message,
                    status_code=response.status_code,
                )
            last_error = _redact(f"HTTP {response.status_code}: {body[:200]}", config)
        except requests.RequestException as exc:
            last_error = _redact(f"{type(exc).__name__}: {exc}", config)

        if attempt < retries:
            wait = 2**attempt
            log.warning(
                "Fallo al enviar WhatsApp (intento %d/%d): %s. Reintento en %ds.",
                attempt,
                retries,
                last_error,
                wait,
            )
            time.sleep(wait)

    log.error("No se pudo enviar el WhatsApp: %s", last_error)
    return NotifyResult(
        sent=False, reason=last_error, message=message, status_code=last_status
    )
