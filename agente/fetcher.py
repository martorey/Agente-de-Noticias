"""Descarga y parseo de feeds RSS/Atom."""

from __future__ import annotations

import concurrent.futures as futures
import logging
import time
from datetime import datetime, timezone

import feedparser
import requests

from .config import Config
from .models import Article, FeedResult
from .sources import Source

log = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (compatible; AgenteDeNoticias/1.0; "
    "+https://github.com/martorey/Agente-de-Noticias)"
)
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "application/rss+xml, application/atom+xml, application/xml;q=0.9, */*;q=0.8",
    "Accept-Language": "es-CL,es;q=0.9,en;q=0.5",
}


def _parse_date(entry) -> datetime | None:
    """Extrae la fecha de publicación como datetime con tzinfo UTC."""
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        parsed = entry.get(key)
        if not parsed:
            continue
        try:
            # feedparser entrega structs en UTC.
            return datetime(*parsed[:6], tzinfo=timezone.utc)
        except (TypeError, ValueError):
            continue
    return None


def _extract_image(entry) -> str:
    """Busca una imagen representativa entre los campos habituales."""
    for media in entry.get("media_content", []) or []:
        url = media.get("url")
        if url:
            return url
    for thumb in entry.get("media_thumbnail", []) or []:
        url = thumb.get("url")
        if url:
            return url
    for link in entry.get("links", []) or []:
        if link.get("rel") == "enclosure" and str(link.get("type", "")).startswith(
            "image/"
        ):
            return link.get("href", "")
    return ""


def _entry_to_article(entry, source: Source) -> Article | None:
    from .processing import clean_text, is_safe_url

    title = clean_text(entry.get("title", ""))
    link = (entry.get("link") or "").strip()
    if not title or not link:
        return None
    if not is_safe_url(link):
        # Los feeds son contenido de terceros: un enlace que no sea http(s)
        # no tiene por qué llegar a la página.
        log.debug("%s: enlace descartado por esquema inseguro: %r", source.name, link)
        return None

    summary = clean_text(entry.get("summary", "") or entry.get("description", ""))
    if len(summary) > 320:
        summary = summary[:317].rstrip() + "…"

    return Article(
        title=title,
        link=link,
        source=source.name,
        section=source.section,
        published=_parse_date(entry),
        summary=summary,
        image=_extract_image(entry),
    )


def fetch_source(
    source: Source, config: Config, session: requests.Session | None = None
) -> tuple[list[Article], FeedResult]:
    """Consulta una fuente probando sus URLs candidatas en orden."""
    started = time.monotonic()
    owns_session = session is None
    session = session or requests.Session()
    last_error = ""

    try:
        for url in source.urls:
            try:
                response = session.get(
                    url, headers=HEADERS, timeout=config.request_timeout
                )
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
                entries = parsed.entries or []
                if not entries:
                    last_error = f"feed sin entradas ({url})"
                    continue

                articles = []
                for entry in entries[: source.max_items]:
                    article = _entry_to_article(entry, source)
                    if article:
                        articles.append(article)

                if not articles:
                    last_error = f"entradas sin título/enlace ({url})"
                    continue

                elapsed = int((time.monotonic() - started) * 1000)
                log.info(
                    "%s: %d noticias desde %s (%d ms)",
                    source.name,
                    len(articles),
                    url,
                    elapsed,
                )
                return articles, FeedResult(
                    source_name=source.name,
                    section=source.section,
                    ok=True,
                    url_used=url,
                    article_count=len(articles),
                    elapsed_ms=elapsed,
                )
            except requests.RequestException as exc:
                last_error = f"{type(exc).__name__}: {exc}"
            except Exception as exc:  # feedparser/XML rotos no deben tumbar la corrida
                last_error = f"{type(exc).__name__}: {exc}"
    finally:
        if owns_session:
            session.close()

    elapsed = int((time.monotonic() - started) * 1000)
    log.warning("%s: sin datos (%s)", source.name, last_error)
    return [], FeedResult(
        source_name=source.name,
        section=source.section,
        ok=False,
        error=last_error or "sin resultado",
        elapsed_ms=elapsed,
    )


def fetch_all(
    sources: list[Source], config: Config
) -> tuple[list[Article], list[FeedResult]]:
    """Consulta todas las fuentes en paralelo y devuelve noticias + diagnóstico."""
    articles: list[Article] = []
    results: list[FeedResult] = []

    workers = max(1, min(config.max_workers, len(sources) or 1))
    with futures.ThreadPoolExecutor(max_workers=workers) as pool:
        pending = {
            pool.submit(fetch_source, source, config): source for source in sources
        }
        for future in futures.as_completed(pending):
            source = pending[future]
            try:
                found, result = future.result()
            except Exception as exc:  # red de seguridad
                found, result = [], FeedResult(
                    source_name=source.name,
                    section=source.section,
                    ok=False,
                    error=f"{type(exc).__name__}: {exc}",
                )
            articles.extend(found)
            results.append(result)

    results.sort(key=lambda r: (r.section, r.source_name))
    return articles, results
