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
    # Un agregador titula "Titular - Medio". Cuando esto es True se extrae el
    # medio real del sufijo, para no atribuirle todo al agregador.
    aggregator: bool = False
    # Por qué una fuente está apagada; aparece en el diagnóstico.
    disabled_reason: str = ""

    @property
    def slug(self) -> str:
        return "".join(c if c.isalnum() else "-" for c in self.name.lower()).strip("-")


# Estado verificado el 2026-08-11 con el workflow "Diagnóstico de fuentes"
# (modo `descubrir`). Las rutas no son las obvias: varios medios chilenos usan
# la plataforma Arc (/arc/outboundfeeds/rss/) o FeedBurner.

# --- Chile ------------------------------------------------------------------

CHILE: tuple[Source, ...] = (
    Source(
        name="La Tercera",
        section=NACIONAL,
        urls=(
            "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
            "https://www.latercera.com/feed/",
        ),
        homepage="https://www.latercera.com",
        max_items=30,
    ),
    Source(
        name="ADN Radio",
        section=NACIONAL,
        urls=(
            "https://www.adnradio.cl/arc/outboundfeeds/rss/?outputType=xml",
            "https://www.adnradio.cl/feed/",
        ),
        homepage="https://www.adnradio.cl",
        max_items=30,
    ),
    Source(
        name="BioBioChile",
        section=NACIONAL,
        urls=(
            "https://feeds.feedburner.com/radiobiobio/NNeJ",
            "https://www.biobiochile.cl/lista/rss/nacional",
        ),
        homepage="https://www.biobiochile.cl",
        max_items=25,
    ),
    Source(
        name="Ex-Ante",
        section=NACIONAL,
        urls=("https://www.ex-ante.cl/feed/",),
        homepage="https://www.ex-ante.cl",
        max_items=12,
    ),
    Source(
        name="La Nación",
        section=NACIONAL,
        urls=("https://www.lanacion.cl/feed/",),
        homepage="https://www.lanacion.cl",
        max_items=12,
    ),
    # Emol, T13, Cooperativa y El Mostrador bloquean el acceso directo a su RSS.
    # Google News sí los indexa, así que entran por aquí; el medio real se toma
    # del sufijo del titular.
    Source(
        name="Google News Chile",
        section=NACIONAL,
        urls=(
            "https://news.google.com/rss/headlines/section/topic/NATION"
            "?hl=es-419&gl=CL&ceid=CL:es",
            "https://news.google.com/rss?hl=es-419&gl=CL&ceid=CL:es",
        ),
        homepage="https://news.google.com",
        max_items=30,
        aggregator=True,
    ),
    # --- Sin feed accesible al 2026-08-11 -----------------------------------
    # Se dejan declaradas para que el diagnóstico semanal las siga revisando:
    # si vuelven a publicar RSS, basta con poner enabled=True.
    Source(
        name="Emol",
        section=NACIONAL,
        urls=(
            "https://www.emol.com/rss/rss.asp?canal=onlinenacional",
            "https://www.emol.com/rss/rss.asp?canal=noticias",
        ),
        homepage="https://www.emol.com",
        enabled=False,
        disabled_reason="corta la conexión (reset)",
    ),
    Source(
        name="T13",
        section=NACIONAL,
        urls=("https://www.t13.cl/rss/nacional", "https://www.t13.cl/feed"),
        homepage="https://www.t13.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="Cooperativa",
        section=NACIONAL,
        urls=("https://www.cooperativa.cl/noticias/site/tax/port/all/rss_2_0.xml",),
        homepage="https://www.cooperativa.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="El Mostrador",
        section=NACIONAL,
        urls=("https://www.elmostrador.cl/feed/",),
        homepage="https://www.elmostrador.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="24 Horas",
        section=NACIONAL,
        urls=("https://www.24horas.cl/rss/nacional",),
        homepage="https://www.24horas.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="CNN Chile",
        section=NACIONAL,
        urls=("https://www.cnnchile.com/feed/",),
        homepage="https://www.cnnchile.com",
        enabled=False,
        disabled_reason="feed sin entradas",
    ),
    Source(
        name="Meganoticias",
        section=NACIONAL,
        urls=("https://www.meganoticias.cl/rss/nacional.xml",),
        homepage="https://www.meganoticias.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="El Dínamo",
        section=NACIONAL,
        urls=("https://www.eldinamo.cl/feed/",),
        homepage="https://www.eldinamo.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="Diario Financiero",
        section=NACIONAL,
        urls=("https://www.df.cl/rss",),
        homepage="https://www.df.cl",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
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
        max_items=30,
    ),
    Source(
        name="Euronews",
        section=INTERNACIONAL,
        urls=("https://es.euronews.com/rss",),
        homepage="https://es.euronews.com",
        max_items=25,
    ),
    Source(
        name="France 24",
        section=INTERNACIONAL,
        urls=("https://www.france24.com/es/rss",),
        homepage="https://www.france24.com/es",
        max_items=24,
    ),
    Source(
        name="El País",
        section=INTERNACIONAL,
        urls=(
            # La de internacional viene más acotada al tema que la portada.
            "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/section/internacional/portada",
            "https://feeds.elpais.com/mrss-s/pages/ep/site/elpais.com/portada",
        ),
        homepage="https://elpais.com/internacional/",
        max_items=25,
    ),
    Source(
        name="DW Español",
        section=INTERNACIONAL,
        urls=(
            "https://rss.dw.com/rdf/rss-sp-all",
            "https://rss.dw.com/xml/rss-sp-all",
        ),
        homepage="https://www.dw.com/es",
        max_items=20,
    ),
    Source(
        name="Infobae",
        section=INTERNACIONAL,
        urls=(
            "https://www.infobae.com/arc/outboundfeeds/rss/category/america/mundo/",
            "https://www.infobae.com/america/feeds/rss/",
        ),
        homepage="https://www.infobae.com/america/",
        max_items=20,
    ),
    Source(
        name="Google News Mundo",
        section=INTERNACIONAL,
        urls=(
            "https://news.google.com/rss/headlines/section/topic/WORLD"
            "?hl=es-419&gl=CL&ceid=CL:es",
        ),
        homepage="https://news.google.com",
        max_items=25,
        aggregator=True,
    ),
    # En inglés: habilitar con FUENTES_EXTRA si se quieren.
    Source(
        name="Al Jazeera",
        section=INTERNACIONAL,
        urls=("https://www.aljazeera.com/xml/rss/all.xml",),
        homepage="https://www.aljazeera.com",
        enabled=False,
        disabled_reason="en inglés",
        tags=("inglés",),
    ),
    Source(
        name="The Guardian",
        section=INTERNACIONAL,
        urls=("https://www.theguardian.com/world/rss",),
        homepage="https://www.theguardian.com/world",
        enabled=False,
        disabled_reason="en inglés",
        tags=("inglés",),
    ),
    Source(
        name="CNN Español",
        section=INTERNACIONAL,
        urls=("https://cnnespanol.cnn.com/feed/",),
        homepage="https://cnnespanol.cnn.com",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
    ),
    Source(
        name="swissinfo",
        section=INTERNACIONAL,
        urls=("https://www.swissinfo.ch/service/rss/spa/rss.xml",),
        homepage="https://www.swissinfo.ch/spa/",
        enabled=False,
        disabled_reason="404 en todas las rutas probadas",
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
