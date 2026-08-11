"""Estructuras de datos compartidas."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Article:
    """Una noticia normalizada, ya independiente del formato del feed."""

    title: str
    link: str
    source: str
    section: str
    published: datetime | None = None
    summary: str = ""
    image: str = ""
    # Otros medios que publicaron la misma historia (se llena al agrupar).
    also_in: list[str] = field(default_factory=list)
    # uids de las versiones duplicadas que se fusionaron en ésta.
    merged_uids: list[str] = field(default_factory=list)

    @property
    def uid(self) -> str:
        """Identificador estable de la noticia, usado para detectar novedades."""
        base = f"{self.source}|{self.canonical_link or self.title}"
        return hashlib.sha1(base.encode("utf-8")).hexdigest()[:16]

    @property
    def all_uids(self) -> list[str]:
        """uid propio más los de las versiones fusionadas.

        Una historia cubierta por varios medios se considera conocida si ya se
        vio *cualquiera* de sus versiones: cuál queda como representante depende
        del orden de llegada de los feeds y no debe afectar la detección de
        novedades.
        """
        return [self.uid, *self.merged_uids]

    @property
    def canonical_link(self) -> str:
        from .processing import canonical_url

        return canonical_url(self.link)

    @property
    def corroboration(self) -> int:
        """Cuántos medios cubren la historia (1 = sólo la fuente original)."""
        return 1 + len(self.also_in)


@dataclass
class FeedResult:
    """Resultado de consultar una fuente: sirve para el reporte de salud."""

    source_name: str
    section: str
    ok: bool
    url_used: str = ""
    article_count: int = 0
    error: str = ""
    elapsed_ms: int = 0
