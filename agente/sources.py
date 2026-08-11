"""Catálogo de fuentes RSS.

Cada fuente puede declarar varias URLs candidatas. El fetcher las prueba en
orden y se queda con la primera que devuelva entradas: los medios cambian la
ruta de sus feeds con cierta frecuencia, así que un solo URL fijo es frágil.
"""

from __future__ import annotations

from dataclasses import dataclass, field

NACIONAL = "nacional"
INTERNACIONAL = "internacional"


@dataclass(frozen=True)
class Source:
    """Un medio, con una o más URLs de feed candidatas."""

    name: str
    section: str
    urls: tuple[str, ...]
    homepage: str = ""
    enabled: bool = True
    # Los feeds generalistas mezclan secciones; cuando un medio publica mucho
    # ruido (deportes, farándula) se puede limitar cuántas entradas aporta.
    max_items: int = 25
    tags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def slug(self) -> str:
        return "".join(c if c.isalnum() else "-" for c in self.name.lower()).strip("-")


# --- Chile ------------------------------------------------------------------

CHILE: tuple[Source, ...] = (
    Source(
        name="Emol",
        section=NACIONAL,
        urls=(
            "https://www.emol.com/rss/rss.asp?canal=onlinenacional",
            "https://www.emol.com/rss/rss.asp?canal=noticias",
        ),
        homepage="https://www.emol.com",
    ),
    Source(
        name="BioBioChile",
        section=NACIONAL,
        urls=(
            "https://www.biobiochile.cl/lista/rss/nacional",
            "https://www.biobiochile.cl/rss/nacional.xml",
            "https://www.biobiochile.cl/feed",
        ),
        homepage="https://www.biobiochile.cl",
    ),
    Source(
        name="La Tercera",
        section=NACIONAL,
        urls=(
            "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
            "https://www.latercera.com/feed/",
            "https://www.latercera.com/arcio/rss/",
        ),
        homepage="https://www.latercera.com",
    ),
    Source(
        name="Cooperativa",
        section=NACIONAL,
        urls=(
            "https://www.cooperativa.cl/noticias/site/tax/port/all/rss_2_0.xml",
            "https://www.cooperativa.cl/noticias/site/edic/base/port/rss.xml",
        ),
        homepage="https://www.cooperativa.cl",
    ),
    Source(
        name="T13",
        section=NACIONAL,
        urls=(
            "https://www.t13.cl/rss/nacional",
            "https://www.t13.cl/feed",
            "https://www.t13.cl/rss",
        ),
        homepage="https://www.t13.cl",
    ),
    Source(
        name="El Mostrador",
        section=NACIONAL,
        urls=("https://www.elmostrador.cl/feed/",),
        homepage="https://www.elmostrador.cl",
    ),
    Source(
        name="24 Horas",
        section=NACIONAL,
        urls=(
            "https://www.24horas.cl/rss/nacional",
            "https://www.24horas.cl/feed",
        ),
        homepage="https://www.24horas.cl",
    ),
    Source(
        name="ADN Radio",
        section=NACIONAL,
        urls=("https://www.adnradio.cl/feed/",),
        homepage="https://www.adnradio.cl",
    ),
    Source(
        name="CNN Chile",
        section=NACIONAL,
        urls=("https://www.cnnchile.com/feed/",),
        homepage="https://www.cnnchile.com",
    ),
    Source(
        name="La Nación",
        section=NACIONAL,
        urls=("https://www.lanacion.cl/feed/",),
        homepage="https://www.lanacion.cl",
    ),
    Source(
        name="El Dínamo",
        section=NACIONAL,
        urls=("https://www.eldinamo.cl/feed/",),
        homepage="https://www.eldinamo.cl",
    ),
    Source(
        name="Ex-Ante",
        section=NACIONAL,
        urls=("https://www.ex-ante.cl/feed/",),
        homepage="https://www.ex-ante.cl",
    ),
    Source(
        name="Meganoticias",
        section=NACIONAL,
        urls=(
            "https://www.meganoticias.cl/rss/nacional.xml",
            "https://www.meganoticias.cl/feed",
        ),
        homepage="https://www.meganoticias.cl",
    ),
    Source(
        name="Diario Financiero",
        section=NACIONAL,
        urls=("https://www.df.cl/rss", "https://www.df.cl/feed"),
        homepage="https://www.df.cl",
        max_items=12,
        tags=("economía",),
    ),
)


# --- Internacional ----------------------------------------------------------

INTERNACIONAL_SOURCES: tuple[Source, ...] = (
    Source(
        name="BBC Mundo",
        section=INTERNACIONAL,
        urls=("https://feeds.bbci.co.uk/mundo/rss.xml",),
        homepage="https://www.bbc.com/mundo",
    ),
    Source(
        name="DW Español",
        section=INTERNACIONAL,
        urls=(
            "https://rss.dw.com/rdf/rss-sp-all",
            "https://rss.dw.com/xml/rss-sp-all",
        ),
        homepage="https://www.dw.com/es",
    ),
    Source(
        name="France 24",
        section=INTERNACIONAL,
        urls=("https://www.france24.com/es/rss",),
        homepage="https://www.france24.com/es",
    ),
    Source(
        name="Euronews",
        section=INTERNACIONAL,
        urls=(
            "https://es.euronews.com/rss",
            "https://es.euronews.com/rss?level=theme&name=news",
        ),
        homepage="https://es.euronews.com",
    ),
    Source(
        name="CNN Español",
        section=INTERNACIONAL,
        urls=("https://cnnespanol.cnn.com/feed/",),
        homepage="https://cnnespanol.cnn.com",
    ),
    Source(
        name="El País",
        section=INTERNACIONAL,
        urls=(
            "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
            "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
        ),
        homepage="https://elpais.com/internacional/",
    ),
    Source(
        name="Infobae",
        section=INTERNACIONAL,
        urls=(
            "https://www.infobae.com/america/feeds/rss/",
            "https://www.infobae.com/feeds/rss/",
        ),
        homepage="https://www.infobae.com/america/",
        max_items=15,
    ),
    Source(
        name="swissinfo",
        section=INTERNACIONAL,
        urls=("https://www.swissinfo.ch/service/rss/spa/rss.xml",),
        homepage="https://www.swissinfo.ch/spa/",
        max_items=10,
    ),
    Source(
        name="Al Jazeera",
        section=INTERNACIONAL,
        urls=("https://www.aljazeera.com/xml/rss/all.xml",),
        homepage="https://www.aljazeera.com",
        enabled=False,  # en inglés: habilitar con FUENTES_EXTRA=Al Jazeera
        tags=("inglés",),
    ),
    Source(
        name="The Guardian",
        section=INTERNACIONAL,
        urls=("https://www.theguardian.com/world/rss",),
        homepage="https://www.theguardian.com/world",
        enabled=False,  # en inglés
        tags=("inglés",),
    ),
)


ALL_SOURCES: tuple[Source, ...] = CHILE + INTERNACIONAL_SOURCES


def active_sources(
    extra: frozenset[str] = frozenset(),
    excluded: frozenset[str] = frozenset(),
) -> list[Source]:
    """Fuentes habilitadas, con overrides por nombre (case-insensitive)."""
    extra_lower = {name.strip().lower() for name in extra if name.strip()}
    excluded_lower = {name.strip().lower() for name in excluded if name.strip()}

    chosen = []
    for source in ALL_SOURCES:
        name = source.name.lower()
        if name in excluded_lower:
            continue
        if source.enabled or name in extra_lower:
            chosen.append(source)
    return chosen
