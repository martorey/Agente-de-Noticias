"""Generación de la página HTML pública."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Config
from .models import Article, FeedResult

SECTION_LABELS = {
    "nacional": "Chile",
    "internacional": "Internacional",
}

_CSS = """
*, *::before, *::after { box-sizing: border-box; }

:root {
  color-scheme: light dark;
  --bg: #f6f7f9;
  --surface: #ffffff;
  --surface-alt: #f0f2f5;
  --border: #e3e6ea;
  --text: #16191d;
  --text-muted: #626973;
  --text-faint: #8b929c;
  --accent: #b3261e;
  --accent-soft: #fdecea;
  --shadow: 0 1px 2px rgba(16, 20, 26, .06), 0 4px 12px rgba(16, 20, 26, .04);
  --radius: 12px;
  --max-width: 1180px;
}

@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0f1216;
    --surface: #171b21;
    --surface-alt: #1e242c;
    --border: #2a313a;
    --text: #e9edf2;
    --text-muted: #a3acb8;
    --text-faint: #78828f;
    --accent: #ff6b5e;
    --accent-soft: #2a1a19;
    --shadow: 0 1px 2px rgba(0, 0, 0, .4), 0 4px 14px rgba(0, 0, 0, .3);
  }
}

body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto,
               "Helvetica Neue", Arial, sans-serif;
  line-height: 1.55;
  -webkit-font-smoothing: antialiased;
}

.wrap { max-width: var(--max-width); margin: 0 auto; padding: 0 20px; }

header.site {
  background: var(--surface);
  border-bottom: 1px solid var(--border);
  padding: 28px 0 0;
  position: sticky; top: 0; z-index: 10;
  backdrop-filter: saturate(180%) blur(8px);
}
.masthead { display: flex; flex-wrap: wrap; align-items: baseline; gap: 12px 16px; }
h1 {
  margin: 0; font-size: 1.6rem; letter-spacing: -.02em; font-weight: 700;
}
h1 .dot { color: var(--accent); }
.updated { color: var(--text-muted); font-size: .875rem; margin: 0; }
.updated strong { color: var(--text); font-weight: 600; }

nav.sections { display: flex; gap: 4px; margin: 18px 0 0; overflow-x: auto; }
nav.sections a {
  padding: 9px 14px; border-radius: 8px 8px 0 0; text-decoration: none;
  color: var(--text-muted); font-size: .9rem; font-weight: 600; white-space: nowrap;
  border-bottom: 2px solid transparent;
}
nav.sections a:hover { color: var(--text); background: var(--surface-alt); }
nav.sections a .count { color: var(--text-faint); font-weight: 500; }

main { padding: 32px 0 8px; }
section.block { margin-bottom: 44px; scroll-margin-top: 130px; }
.block-head {
  display: flex; align-items: center; gap: 12px; margin-bottom: 18px;
}
.block-head h2 {
  margin: 0; font-size: 1.15rem; font-weight: 700; letter-spacing: -.01em;
}
.block-head .rule { flex: 1; height: 1px; background: var(--border); }
.block-head .n { color: var(--text-faint); font-size: .85rem; font-variant-numeric: tabular-nums; }

.grid {
  display: grid; gap: 14px;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  align-items: start; /* que cada tarjeta mida lo que su contenido */
}

article.card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: var(--radius); padding: 16px 18px; box-shadow: var(--shadow);
  display: flex; flex-direction: column; gap: 8px;
  transition: transform .12s ease, box-shadow .12s ease;
}
article.card:hover { transform: translateY(-1px); box-shadow: 0 2px 4px rgba(16,20,26,.08), 0 8px 20px rgba(16,20,26,.07); }
article.card.lead { grid-column: span 2; }
@media (max-width: 720px) { article.card.lead { grid-column: span 1; } }

.meta { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; font-size: .78rem; }
.source {
  font-weight: 700; color: var(--accent); text-transform: uppercase;
  letter-spacing: .04em; font-size: .72rem;
}
.time { color: var(--text-faint); font-variant-numeric: tabular-nums; }
.badge {
  background: var(--accent-soft); color: var(--accent); border-radius: 99px;
  padding: 2px 8px; font-size: .7rem; font-weight: 700;
}

h3.headline { margin: 0; font-size: 1.02rem; line-height: 1.35; font-weight: 650; letter-spacing: -.01em; }
article.card.lead h3.headline { font-size: 1.2rem; }
h3.headline a { color: inherit; text-decoration: none; }
h3.headline a:hover { color: var(--accent); text-decoration: underline; text-underline-offset: 2px; }

p.summary {
  margin: 0; color: var(--text-muted); font-size: .9rem;
  display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden;
}
.also { color: var(--text-faint); font-size: .76rem; margin: 0; }

.empty {
  background: var(--surface); border: 1px dashed var(--border); border-radius: var(--radius);
  padding: 28px; text-align: center; color: var(--text-muted);
}

footer.site {
  border-top: 1px solid var(--border); margin-top: 20px; padding: 22px 0 44px;
  color: var(--text-faint); font-size: .82rem;
}
footer.site p { margin: 0 0 8px; }
details.health summary { cursor: pointer; color: var(--text-muted); font-weight: 600; }
details.health ul { margin: 10px 0 0; padding-left: 18px; columns: 2; }
@media (max-width: 640px) { details.health ul { columns: 1; } }
details.health li { margin-bottom: 3px; }
.fail { color: var(--accent); }
"""

_JS = """
// Marca los tiempos como relativos y los mantiene frescos sin recargar.
(function () {
  var RTF = window.Intl && Intl.RelativeTimeFormat
    ? new Intl.RelativeTimeFormat('es', { numeric: 'auto' }) : null;

  function relative(iso) {
    var then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    var mins = Math.round((then - Date.now()) / 60000);
    if (!RTF) return Math.abs(mins) + ' min';
    var abs = Math.abs(mins);
    if (abs < 60) return RTF.format(mins, 'minute');
    var hours = Math.round(mins / 60);
    if (Math.abs(hours) < 24) return RTF.format(hours, 'hour');
    return RTF.format(Math.round(hours / 24), 'day');
  }

  function tick() {
    document.querySelectorAll('[data-ts]').forEach(function (el) {
      var text = relative(el.getAttribute('data-ts'));
      if (text) el.textContent = text;
    });
  }

  tick();
  setInterval(tick, 60000);
})();
"""


def _fmt_local(dt: datetime, tz: ZoneInfo) -> str:
    return dt.astimezone(tz).strftime("%H:%M")


def _fmt_full(dt: datetime, tz: ZoneInfo) -> str:
    local = dt.astimezone(tz)
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = [
        "enero", "febrero", "marzo", "abril", "mayo", "junio",
        "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
    ]
    return (
        f"{dias[local.weekday()]} {local.day} de {meses[local.month - 1]}, "
        f"{local.strftime('%H:%M')}"
    )


def _safe_href(url: str) -> str:
    """href sólo si el esquema es http/https; si no, enlace inerte."""
    from .processing import is_safe_url

    return escape(url, quote=True) if is_safe_url(url) else "#"


def _card(article: Article, tz: ZoneInfo, lead: bool = False) -> str:
    classes = "card lead" if lead else "card"
    bits = [f'<article class="{classes}">', '<div class="meta">']
    bits.append(f'<span class="source">{escape(article.source)}</span>')

    if article.published:
        iso = article.published.isoformat()
        bits.append(
            f'<span class="time" data-ts="{escape(iso)}" '
            f'title="{escape(_fmt_full(article.published, tz))}">'
            f"{escape(_fmt_local(article.published, tz))}</span>"
        )

    if article.corroboration >= 3:
        bits.append(f'<span class="badge">{article.corroboration} medios</span>')

    bits.append("</div>")
    bits.append(
        '<h3 class="headline"><a href="{href}" target="_blank" rel="noopener noreferrer">'
        "{title}</a></h3>".format(
            href=_safe_href(article.link), title=escape(article.title)
        )
    )

    if article.summary:
        bits.append(f'<p class="summary">{escape(article.summary)}</p>')

    if article.also_in:
        otros = ", ".join(escape(s) for s in sorted(article.also_in)[:4])
        bits.append(f'<p class="also">También en {otros}</p>')

    bits.append("</article>")
    return "".join(bits)


def _section_block(section: str, articles: list[Article], tz: ZoneInfo) -> str:
    label = SECTION_LABELS.get(section, section.capitalize())
    parts = [
        f'<section class="block" id="{escape(section)}">',
        '<div class="block-head">',
        f"<h2>{escape(label)}</h2>",
        '<span class="rule"></span>',
        f'<span class="n">{len(articles)}</span>',
        "</div>",
    ]

    if not articles:
        parts.append(
            '<div class="empty">No se pudieron recuperar noticias de esta sección '
            "en la última actualización.</div>"
        )
    else:
        parts.append('<div class="grid">')
        for index, article in enumerate(articles):
            parts.append(_card(article, tz, lead=index == 0))
        parts.append("</div>")

    parts.append("</section>")
    return "".join(parts)


def _health_block(results: list[FeedResult]) -> str:
    if not results:
        return ""
    ok = [r for r in results if r.ok]
    items = []
    for result in sorted(results, key=lambda r: (r.ok, r.source_name)):
        if result.ok:
            items.append(
                f"<li>{escape(result.source_name)} — {result.article_count} titulares</li>"
            )
        else:
            items.append(
                f'<li class="fail">{escape(result.source_name)} — sin datos '
                f"({escape(result.error[:90])})</li>"
            )
    return (
        '<details class="health"><summary>Fuentes consultadas: '
        f"{len(ok)} de {len(results)} respondieron</summary>"
        f"<ul>{''.join(items)}</ul></details>"
    )


def render_page(
    grouped: dict[str, list[Article]],
    results: list[FeedResult],
    config: Config,
    generated_at: datetime | None = None,
) -> str:
    """Arma el HTML completo de la página."""
    generated_at = generated_at or datetime.now(timezone.utc)
    tz = config.tz
    total = sum(len(items) for items in grouped.values())

    order = [s for s in ("nacional", "internacional") if s in grouped]
    order += [s for s in grouped if s not in order]

    nav = "".join(
        '<a href="#{id}">{label} <span class="count">{n}</span></a>'.format(
            id=escape(s),
            label=escape(SECTION_LABELS.get(s, s.capitalize())),
            n=len(grouped.get(s, [])),
        )
        for s in order
    )
    blocks = "".join(_section_block(s, grouped.get(s, []), tz) for s in order)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Titulares nacionales e internacionales, actualizados automáticamente.">
<meta name="robots" content="noindex">
<meta property="og:title" content="{escape(config.site_title)}">
<meta property="og:description" content="{total} titulares · actualizado {escape(_fmt_full(generated_at, tz))}">
<meta property="og:type" content="website">
<title>{escape(config.site_title)} · {escape(_fmt_local(generated_at, tz))}</title>
<link rel="icon" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'><text y='.9em' font-size='90'>📰</text></svg>">
<style>{_CSS}</style>
</head>
<body>
<header class="site">
  <div class="wrap">
    <div class="masthead">
      <h1>{escape(config.site_title)}<span class="dot">.</span></h1>
      <p class="updated">Actualizado <strong data-ts="{escape(generated_at.isoformat())}">{escape(_fmt_local(generated_at, tz))}</strong>
      · {escape(_fmt_full(generated_at, tz))} · {total} titulares</p>
    </div>
    <nav class="sections">{nav}</nav>
  </div>
</header>
<main class="wrap">{blocks}</main>
<footer class="site">
  <div class="wrap">
    <p>Se actualiza automáticamente. Los titulares y enlaces pertenecen a sus medios.</p>
    {_health_block(results)}
  </div>
</footer>
<script>{_JS}</script>
</body>
</html>
"""


def write_site(
    grouped: dict[str, list[Article]],
    results: list[FeedResult],
    config: Config,
    generated_at: datetime | None = None,
) -> Path:
    """Escribe index.html y un feed.json con los mismos datos."""
    generated_at = generated_at or datetime.now(timezone.utc)
    out_dir = Path(config.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    index = out_dir / "index.html"
    index.write_text(
        render_page(grouped, results, config, generated_at), encoding="utf-8"
    )

    payload = {
        "generado": generated_at.isoformat(),
        "total": sum(len(v) for v in grouped.values()),
        "secciones": {
            section: [
                {
                    "titulo": a.title,
                    "enlace": a.link,
                    "fuente": a.source,
                    "publicado": a.published.isoformat() if a.published else None,
                    "resumen": a.summary,
                    "tambien_en": a.also_in,
                }
                for a in articles
            ]
            for section, articles in grouped.items()
        },
        "fuentes": [
            {
                "nombre": r.source_name,
                "ok": r.ok,
                "titulares": r.article_count,
                "error": r.error,
            }
            for r in results
        ],
    }
    (out_dir / "feed.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # .nojekyll evita que GitHub Pages procese la salida con Jekyll.
    (out_dir / ".nojekyll").write_text("", encoding="utf-8")
    return index
