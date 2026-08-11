"""Descubrimiento de feeds RSS.

El entorno de desarrollo no siempre tiene salida a internet, y los medios
cambian sus rutas. Este módulo corre en el runner de Actions, parte de la
portada de cada medio y reporta qué URL de feed funciona de verdad.

    python -m agente.main descubrir
"""

from __future__ import annotations

import concurrent.futures as futures
import re
from dataclasses import dataclass, field

import feedparser
import requests

from .sources import ALL_SOURCES, Source

# Varios medios rechazan clientes que no parecen un navegador: responden 404,
# 403 o directamente cortan la conexión. Se prueban en orden.
USER_AGENTS = (
    (
        "navegador",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    ),
    (
        "lector",
        "Feedly/1.0 (+https://feedly.com/fetcher.html; like FeedFetcher-Google)",
    ),
    ("agente", "Mozilla/5.0 (compatible; AgenteDeNoticias/1.0)"),
)

# Rutas habituales, ordenadas de más a menos probable.
COMMON_PATHS = (
    "/feed/",
    "/rss",
    "/rss.xml",
    "/feed.xml",
    "/rss/",
    "/index.xml",
    "/atom.xml",
    "/feeds/rss.xml",
    "/arc/outboundfeeds/rss/?outputType=xml",
    "/rss/portada.xml",
    "/rss/noticias.xml",
)

_LINK_RE = re.compile(
    r"""<link[^>]+type\s*=\s*["']application/(?:rss|atom)\+xml["'][^>]*>""",
    re.IGNORECASE,
)
_HREF_RE = re.compile(r"""href\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


@dataclass
class Candidate:
    url: str
    ua_label: str
    entries: int
    sample: str = ""


@dataclass
class Discovery:
    source_name: str
    section: str
    working: list[Candidate] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def _probe(url: str, ua_label: str, ua: str, timeout: int = 15) -> Candidate | None:
    """Devuelve un candidato si la URL entrega un feed con entradas."""
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": ua,
                "Accept": "application/rss+xml, application/atom+xml, "
                "application/xml;q=0.9, text/html;q=0.8, */*;q=0.7",
                "Accept-Language": "es-CL,es;q=0.9",
            },
            timeout=timeout,
        )
        if not response.ok:
            return None
        parsed = feedparser.parse(response.content)
        if not parsed.entries:
            return None
        titulo = ""
        primera = parsed.entries[0]
        if primera.get("title"):
            titulo = str(primera["title"])[:70]
        return Candidate(
            url=response.url, ua_label=ua_label, entries=len(parsed.entries), sample=titulo
        )
    except Exception:
        return None


def _autodiscover(homepage: str, ua: str, timeout: int = 15) -> list[str]:
    """Lee los <link rel=alternate type=application/rss+xml> de la portada."""
    try:
        response = requests.get(
            homepage, headers={"User-Agent": ua}, timeout=timeout
        )
        if not response.ok:
            return []
        html = response.text
    except Exception:
        return []

    encontrados = []
    for tag in _LINK_RE.findall(html):
        match = _HREF_RE.search(tag)
        if not match:
            continue
        href = match.group(1).strip()
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = homepage.rstrip("/") + href
        elif not href.startswith("http"):
            href = homepage.rstrip("/") + "/" + href
        if href not in encontrados:
            encontrados.append(href)
    return encontrados[:8]


def discover_source(source: Source, max_hits: int = 3) -> Discovery:
    """Busca feeds vivos para un medio: primero los declarados, luego la portada."""
    result = Discovery(source_name=source.name, section=source.section)
    base = source.homepage or (
        source.urls[0].split("/")[0] + "//" + source.urls[0].split("/")[2]
        if source.urls
        else ""
    )

    vistos: set[str] = set()

    def intentar(urls: list[str], etiqueta: str) -> None:
        for url in urls:
            if url in vistos or len(result.working) >= max_hits:
                continue
            vistos.add(url)
            for ua_label, ua in USER_AGENTS:
                hit = _probe(url, ua_label)
                if hit:
                    result.working.append(hit)
                    if etiqueta:
                        result.notes.append(f"{etiqueta}: {url}")
                    break

    # 1. Las URLs que ya están configuradas.
    intentar(list(source.urls), "")

    # 2. Autodiscovery desde la portada.
    if len(result.working) < max_hits and base:
        for _, ua in USER_AGENTS[:1]:
            enlaces = _autodiscover(base, ua)
            if enlaces:
                result.notes.append(f"portada declara {len(enlaces)} feed(s)")
                intentar(enlaces, "autodiscovery")
                break

    # 3. Rutas habituales.
    if len(result.working) < max_hits and base:
        intentar([base.rstrip("/") + p for p in COMMON_PATHS], "ruta común")

    if not result.working:
        result.notes.append("sin feed detectado")
    return result


def discover_all(sources: list[Source] | None = None) -> list[Discovery]:
    sources = sources if sources is not None else list(ALL_SOURCES)
    resultados: list[Discovery] = []
    with futures.ThreadPoolExecutor(max_workers=6) as pool:
        for discovery in pool.map(discover_source, sources):
            resultados.append(discovery)
    resultados.sort(key=lambda d: (d.section, d.source_name))
    return resultados
