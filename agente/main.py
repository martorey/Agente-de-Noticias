"""Punto de entrada: orquesta recolección, publicación y aviso."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import os
import sys
from datetime import datetime, timezone

from . import __version__
from .config import Config
from .fetcher import fetch_all
from .models import Article
from .notifier import build_message, page_url, send_whatsapp
from .processing import prepare
from .render import write_site
from .sources import active_sources
from . import state as state_mod

log = logging.getLogger("agente")


def _setup_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _github_summary(lines: list[str]) -> None:
    """Escribe un resumen en la pestaña de la corrida de GitHub Actions."""
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("\n".join(lines) + "\n")
    except OSError as exc:
        log.debug("No se pudo escribir el resumen de Actions: %s", exc)


def run(config: Config) -> int:
    """Corrida completa: recolectar, publicar y avisar."""
    generated_at = datetime.now(timezone.utc)
    sources = active_sources(config.extra_sources, config.excluded_sources)
    log.info("Consultando %d fuentes…", len(sources))

    raw, results = fetch_all(sources, config)
    ok_count = sum(1 for r in results if r.ok)
    log.info(
        "%d titulares en bruto desde %d/%d fuentes.", len(raw), ok_count, len(results)
    )

    if not raw:
        log.error("Ninguna fuente devolvió noticias; no se publica ni se avisa.")
        _github_summary(
            [
                "## ❌ Agente de noticias",
                "",
                "Ninguna fuente respondió. La página anterior se mantiene sin cambios.",
                "",
                *[f"- `{r.source_name}`: {r.error}" for r in results if not r.ok],
            ]
        )
        return 1

    grouped = prepare(
        raw, config.max_age_hours, config.max_items_per_section, generated_at
    )
    published: list[Article] = [a for items in grouped.values() for a in items]
    log.info(
        "%d noticias tras deduplicar (%s).",
        len(published),
        ", ".join(f"{k}: {len(v)}" for k, v in grouped.items()) or "vacío",
    )

    previous = state_mod.load(config.state_file)
    new_count = state_mod.count_new(published, previous)
    log.info("%d titulares nuevos respecto de la corrida anterior.", new_count)

    index = write_site(grouped, results, config, generated_at)
    log.info("Página escrita en %s", index)

    url = page_url(config, generated_at)
    message = build_message(grouped, config, url, generated_at, new_count)

    should_notify = True
    if config.notify_mode == "solo-nuevas" and new_count < config.notify_min_new:
        should_notify = False
        if new_count == 0:
            log.info("NOTIFY_MODE=solo-nuevas y no hay novedades: no se envía WhatsApp.")
        else:
            log.info(
                "NOTIFY_MODE=solo-nuevas: %d nuevos, por debajo del umbral "
                "(NOTIFY_MIN_NEW=%d); no se envía WhatsApp.",
                new_count,
                config.notify_min_new,
            )

    notify = None
    if should_notify:
        notify = send_whatsapp(message, config)

    state_mod.save(config.state_file, published, previous)

    if notify and notify.sent:
        estado_aviso = "✅ enviado"
    elif not should_notify:
        if new_count == 0:
            estado_aviso = "⏭️ omitido (sin novedades)"
        else:
            estado_aviso = (
                f"⏭️ omitido ({new_count} nuevos, bajo el umbral de "
                f"{config.notify_min_new})"
            )
    elif notify:
        estado_aviso = f"⚠️ no enviado ({notify.reason})"
    else:
        estado_aviso = "—"

    _github_summary(
        [
            "## 📰 Agente de noticias",
            "",
            f"- **Fuentes**: {ok_count}/{len(results)} respondieron",
            f"- **Titulares publicados**: {len(published)} ({new_count} nuevos)",
            f"- **Página**: {url or '(SITE_URL sin configurar)'}",
            f"- **WhatsApp**: {estado_aviso}",
            "",
            *(
                ["<details><summary>Fuentes sin datos</summary>", ""]
                + [f"- `{r.source_name}`: {r.error}" for r in results if not r.ok]
                + ["", "</details>"]
                if ok_count < len(results)
                else []
            ),
        ]
    )

    # Publicar la página es el objetivo principal; un WhatsApp fallido se reporta
    # pero no invalida la corrida (la página ya quedó actualizada).
    if notify and not notify.sent and notify.reason not in {"dry_run", "sin_credenciales"}:
        log.warning("La página se publicó, pero el aviso de WhatsApp falló.")
    return 0


def check_feeds(config: Config) -> int:
    """Diagnóstico: qué fuentes responden y cuáles no."""
    sources = active_sources(config.extra_sources, config.excluded_sources)
    _, results = fetch_all(sources, config)

    ok = [r for r in results if r.ok]
    print(f"\n{len(ok)}/{len(results)} fuentes respondieron\n")
    for result in results:
        if result.ok:
            print(
                f"  ✅ {result.source_name:<20} {result.article_count:>3} titulares  "
                f"{result.elapsed_ms:>5} ms  {result.url_used}"
            )
        else:
            print(f"  ❌ {result.source_name:<20} {result.error}")

    _github_summary(
        [
            "## Diagnóstico de fuentes",
            "",
            f"**{len(ok)}/{len(results)}** respondieron.",
            "",
            "| Fuente | Estado | Titulares | Detalle |",
            "| --- | --- | --- | --- |",
            *[
                f"| {r.source_name} | {'✅' if r.ok else '❌'} | {r.article_count} | "
                f"{r.url_used if r.ok else r.error[:80]} |"
                for r in results
            ],
        ]
    )
    # Falla sólo si no queda ninguna fuente viva.
    return 0 if ok else 1


def discover(config: Config) -> int:
    """Busca las URLs de feed reales de cada medio y las reporta."""
    from .discover import discover_all

    resultados = discover_all()
    vivos = [d for d in resultados if d.working]

    print(f"\n{len(vivos)}/{len(resultados)} medios con feed detectado\n")
    filas = []
    for d in resultados:
        if d.working:
            mejor = max(d.working, key=lambda c: c.entries)
            print(f"  ✅ {d.source_name:<20} {mejor.entries:>3} titulares  {mejor.url}")
            for extra in d.working:
                if extra.url != mejor.url:
                    print(f"     ↳ alternativa: {extra.url} ({extra.entries})")
            if mejor.ua_label != "navegador":
                print(f"     ↳ requiere User-Agent tipo '{mejor.ua_label}'")
            filas.append(
                f"| {d.source_name} | ✅ | {mejor.entries} | `{mejor.url}` | {mejor.ua_label} |"
            )
        else:
            print(f"  ❌ {d.source_name:<20} {'; '.join(d.notes)}")
            filas.append(f"| {d.source_name} | ❌ | 0 | — | {'; '.join(d.notes)} |")

    _github_summary(
        [
            "## Feeds detectados",
            "",
            f"**{len(vivos)}/{len(resultados)}** medios con feed vivo.",
            "",
            "| Medio | Estado | Titulares | URL | Cliente |",
            "| --- | --- | --- | --- | --- |",
            *filas,
        ]
    )
    return 0 if vivos else 1


def preview_message(config: Config) -> int:
    """Muestra el WhatsApp que se enviaría, sin enviarlo."""
    sources = active_sources(config.extra_sources, config.excluded_sources)
    raw, _ = fetch_all(sources, config)
    generated_at = datetime.now(timezone.utc)
    grouped = prepare(
        raw, config.max_age_hours, config.max_items_per_section, generated_at
    )
    url = page_url(config, generated_at)
    print(build_message(grouped, config, url, generated_at))
    return 0


def send_test(config: Config) -> int:
    """Envía un WhatsApp de prueba para validar las credenciales."""
    if not config.whatsapp_configured:
        print(
            "Faltan credenciales: definí CALLMEBOT_PHONE y CALLMEBOT_APIKEY.",
            file=sys.stderr,
        )
        return 2
    message = (
        "*📰 Agente de noticias*\n"
        "Mensaje de prueba: las credenciales de CallMeBot funcionan.\n"
        f"Versión {__version__}"
    )
    result = send_whatsapp(message, config)
    print("Enviado ✅" if result.sent else f"No enviado ❌ — {result.reason}")
    return 0 if result.sent else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="agente",
        description="Agente de noticias: publica una página y avisa por WhatsApp.",
    )
    parser.add_argument(
        "comando",
        nargs="?",
        default="run",
        choices=["run", "check-feeds", "descubrir", "preview", "test-whatsapp"],
        help=(
            "run: corrida completa (por defecto). "
            "check-feeds: diagnóstico de fuentes. "
            "descubrir: busca las URLs de feed reales de cada medio. "
            "preview: muestra el WhatsApp sin enviarlo. "
            "test-whatsapp: envía un mensaje de prueba."
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Log detallado.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No envía WhatsApp (equivale a DRY_RUN=1).",
    )
    parser.add_argument("--version", action="version", version=f"agente {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    _setup_logging(args.verbose)

    config = Config.from_env()
    if args.dry_run:
        config = dataclasses.replace(config, dry_run=True)

    if args.comando == "check-feeds":
        return check_feeds(config)
    if args.comando == "descubrir":
        return discover(config)
    if args.comando == "preview":
        return preview_message(config)
    if args.comando == "test-whatsapp":
        return send_test(config)
    return run(config)


if __name__ == "__main__":
    raise SystemExit(main())
