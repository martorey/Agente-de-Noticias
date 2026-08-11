"""Normalización, deduplicación y ranking de noticias."""

from __future__ import annotations

import html
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from .models import Article

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

# Parámetros de tracking que no cambian el contenido de la nota.
_JUNK_QUERY_PREFIXES = ("utm_", "at_", "ns_", "cmpid", "xtor")
_JUNK_QUERY_KEYS = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "referrer",
    "sh",
    "smid",
}

# Palabras vacías: no aportan a decidir si dos titulares son la misma historia.
_STOPWORDS = {
    "a", "al", "ante", "asi", "aun", "con", "como", "cual", "cuando", "de", "del",
    "desde", "donde", "dos", "el", "ella", "ellos", "en", "entre", "era", "es",
    "esta", "este", "esto", "fue", "ha", "han", "hasta", "hay", "la", "las", "le",
    "les", "lo", "los", "mas", "me", "mi", "muy", "no", "nos", "o", "para", "pero",
    "poco", "por", "porque", "que", "quien", "se", "segun", "ser", "si", "sin",
    "sobre", "solo", "son", "su", "sus", "tan", "te", "tiene", "todo", "tras", "tu",
    "un", "una", "uno", "unos", "y", "ya",
}


def clean_text(raw: str) -> str:
    """Quita HTML y normaliza espacios."""
    if not raw:
        return ""
    text = _TAG_RE.sub(" ", raw)
    text = html.unescape(text)
    text = text.replace("\xa0", " ")
    return _WS_RE.sub(" ", text).strip()


_SAFE_SCHEMES = {"http", "https"}


def is_safe_url(url: str) -> bool:
    """Sólo http/https.

    Escapar el HTML no basta para un enlace: `javascript:...` o `data:...` en un
    href siguen ejecutándose al hacer clic. Los feeds son contenido de terceros,
    así que el esquema se valida antes de renderizar.
    """
    if not url:
        return False
    try:
        scheme = urlsplit(url.strip()).scheme.lower()
    except ValueError:
        return False
    return scheme in _SAFE_SCHEMES


def split_aggregator_title(title: str) -> tuple[str, str]:
    """Separa "Titular - Medio" en (titular, medio).

    Google News anexa el medio al final del titular. Sin separarlo, todas las
    tarjetas se atribuirían al agregador y la deduplicación no reconocería la
    misma noticia venida por el feed directo del medio.

    Devuelve el medio vacío cuando el sufijo no parece un nombre de medio, para
    no mutilar titulares que legítimamente contienen un guion.
    """
    limpio = title.strip()
    if " - " not in limpio:
        return limpio, ""

    cabeza, _, cola = limpio.rpartition(" - ")
    cola = cola.strip()
    cabeza = cabeza.strip()

    # Un nombre de medio es corto, de pocas palabras y no termina en puntuación
    # de frase. El titular restante tiene que seguir siendo un titular.
    if not cabeza or not cola:
        return limpio, ""
    if len(cola) > 32 or len(cola.split()) > 4 or cola[-1] in ".,;:!?":
        return limpio, ""
    if len(cabeza) < 20:
        return limpio, ""
    return cabeza, cola


def canonical_url(url: str) -> str:
    """Normaliza un enlace para comparar: sin tracking, sin fragmento, sin www."""
    if not url:
        return ""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return url.strip()

    host = parts.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    kept = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=False)
        if key.lower() not in _JUNK_QUERY_KEYS
        and not key.lower().startswith(_JUNK_QUERY_PREFIXES)
    ]

    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(kept), ""))


def _strip_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFD", text)
    return "".join(c for c in decomposed if unicodedata.category(c) != "Mn")


def title_tokens(title: str) -> frozenset[str]:
    """Conjunto de palabras significativas de un titular."""
    normalized = _strip_accents(title.lower())
    words = re.findall(r"[a-z0-9]+", normalized)
    return frozenset(w for w in words if len(w) > 2 and w not in _STOPWORDS)


def _similarity(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard sobre las palabras significativas."""
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    if not intersection:
        return 0.0
    return intersection / len(a | b)


# Con titulares muy cortos quedan pocas palabras significativas y dos historias
# distintas pueden dar Jaccard alto por casualidad ("Alza del dólar" vs "Alza del
# cobre"). En ese caso exigimos un parecido casi exacto.
_SHORT_TITLE_TOKENS = 4
_SHORT_TITLE_THRESHOLD = 0.85


def _same_story(a: frozenset[str], b: frozenset[str], threshold: float) -> bool:
    if min(len(a), len(b)) < _SHORT_TITLE_TOKENS:
        threshold = max(threshold, _SHORT_TITLE_THRESHOLD)
    return _similarity(a, b) >= threshold


def _recency_score(article: Article, now: datetime) -> float:
    """1.0 recién publicada, decayendo suavemente con las horas."""
    if article.published is None:
        return 0.35  # sin fecha: ni penalizar de más ni premiar
    hours = max(0.0, (now - article.published).total_seconds() / 3600)
    return 1.0 / (1.0 + hours / 3.0)


def deduplicate(articles: list[Article], threshold: float = 0.6) -> list[Article]:
    """Agrupa noticias repetidas y deja un representante por historia.

    Dos noticias son la misma si comparten enlace canónico, o si sus titulares
    se parecen lo suficiente. El representante conserva en `also_in` los otros
    medios que la cubrieron, lo que además sirve como señal de relevancia.
    """
    representatives: list[Article] = []
    by_link: dict[str, Article] = {}
    token_cache: list[tuple[frozenset[str], Article]] = []

    for article in articles:
        link_key = canonical_url(article.link)
        existing = by_link.get(link_key) if link_key else None

        if existing is None:
            tokens = title_tokens(article.title)
            for other_tokens, other in token_cache:
                if _same_story(tokens, other_tokens, threshold):
                    existing = other
                    break

        if existing is not None:
            if article.source != existing.source and article.source not in existing.also_in:
                existing.also_in.append(article.source)
            if article.uid not in existing.merged_uids:
                existing.merged_uids.append(article.uid)
            # Nos quedamos con el resumen y la imagen más ricos disponibles.
            if len(article.summary) > len(existing.summary):
                existing.summary = article.summary
            if not existing.image and article.image:
                existing.image = article.image
            if article.published and (
                existing.published is None or article.published < existing.published
            ):
                existing.published = article.published
            continue

        representatives.append(article)
        if link_key:
            by_link[link_key] = article
        token_cache.append((title_tokens(article.title), article))

    return representatives


def rank(articles: list[Article], now: datetime | None = None) -> list[Article]:
    """Ordena por relevancia: frescura, con un empujón por cobertura múltiple."""
    now = now or datetime.now(timezone.utc)

    def score(article: Article) -> float:
        # La corroboración entre medios es la mejor señal barata de importancia;
        # se aplica con logaritmo suave para que no aplaste a la frescura.
        corroboration = 1.0 + 0.25 * (article.corroboration - 1)
        return _recency_score(article, now) * corroboration

    return sorted(articles, key=score, reverse=True)


def drop_stale(articles: list[Article], max_age_hours: int, now: datetime | None = None) -> list[Article]:
    """Descarta noticias viejas; las que no traen fecha se conservan."""
    if max_age_hours <= 0:
        return articles
    now = now or datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=max_age_hours)
    return [a for a in articles if a.published is None or a.published >= cutoff]


def stable_order(articles: list[Article]) -> list[Article]:
    """Orden determinista, independiente de cómo respondieron los feeds.

    Las fuentes se consultan en paralelo, así que el orden de llegada varía
    entre corridas. Sin fijarlo, la deduplicación elegiría un representante
    distinto cada vez y la misma historia parecería nueva.
    """
    return sorted(
        articles,
        key=lambda a: (a.section, a.source, canonical_url(a.link), a.title),
    )


def prepare(
    articles: list[Article],
    max_age_hours: int,
    max_per_section: int,
    now: datetime | None = None,
) -> dict[str, list[Article]]:
    """Pipeline completo: limpiar, deduplicar, ordenar y agrupar por sección."""
    now = now or datetime.now(timezone.utc)
    fresh = drop_stale(articles, max_age_hours, now)
    unique = deduplicate(stable_order(fresh))
    ordered = rank(unique, now)

    grouped: dict[str, list[Article]] = {}
    for article in ordered:
        bucket = grouped.setdefault(article.section, [])
        if len(bucket) < max_per_section:
            bucket.append(article)
    return grouped
