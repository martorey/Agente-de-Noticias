from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agente.config import Config  # noqa: E402
from agente.models import Article  # noqa: E402

NOW = datetime(2026, 8, 11, 18, 0, tzinfo=timezone.utc)


@pytest.fixture
def now() -> datetime:
    return NOW


@pytest.fixture
def config(tmp_path) -> Config:
    return Config(
        site_url="https://martorey.github.io/Agente-de-Noticias",
        site_title="Últimas noticias",
        output_dir=str(tmp_path / "public"),
        state_file=str(tmp_path / "estado.json"),
        whatsapp_phone="+56900000000",
        whatsapp_apikey="123456",
        dry_run=True,
    )


def make_article(
    title: str,
    *,
    source: str = "Emol",
    section: str = "nacional",
    link: str | None = None,
    minutes_ago: int | None = 10,
    summary: str = "",
) -> Article:
    published = None if minutes_ago is None else NOW - timedelta(minutes=minutes_ago)
    slug = "".join(c if c.isalnum() else "-" for c in title.lower())[:40]
    return Article(
        title=title,
        link=link or f"https://{source.lower().replace(' ', '')}.cl/{slug}",
        source=source,
        section=section,
        published=published,
        summary=summary,
    )


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
  <channel>
    <title>Medio de prueba</title>
    <item>
      <title>Gobierno anuncia plan de vivienda &amp; empleo</title>
      <link>https://ejemplo.cl/nota-1?utm_source=rss&amp;utm_medium=feed</link>
      <description>&lt;p&gt;El anuncio se realizó esta ma&#241;ana.&lt;/p&gt;</description>
      <pubDate>Tue, 11 Aug 2026 17:30:00 GMT</pubDate>
      <media:content url="https://ejemplo.cl/foto.jpg" />
    </item>
    <item>
      <title>Segunda noticia de prueba</title>
      <link>https://ejemplo.cl/nota-2</link>
      <description>Resumen breve.</description>
      <pubDate>Tue, 11 Aug 2026 16:00:00 GMT</pubDate>
    </item>
    <item>
      <title></title>
      <link>https://ejemplo.cl/sin-titulo</link>
    </item>
  </channel>
</rss>
"""

EMPTY_FEED = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>Vacío</title></channel></rss>
"""
