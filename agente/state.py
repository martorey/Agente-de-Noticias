"""Estado entre corridas: qué noticias ya se vieron.

Permite contar cuántos titulares son realmente nuevos y, si se configura
NOTIFY_MODE=solo-nuevas, evitar mandar un WhatsApp cuando no cambió nada.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from .models import Article

log = logging.getLogger(__name__)

# Cuántos identificadores conservar. Con ~120 uids por corrida cada 30 minutos,
# 3000 cubre alrededor de un día: una historia que sigue en portada no vuelve a
# contarse como nueva.
MAX_REMEMBERED = 3000


@dataclass
class State:
    seen: list[str] = field(default_factory=list)
    last_run: str | None = None

    @property
    def seen_set(self) -> set[str]:
        return set(self.seen)


def load(path: str | Path) -> State:
    file = Path(path)
    if not file.exists():
        return State()
    try:
        raw = json.loads(file.read_text(encoding="utf-8"))
        return State(
            seen=list(raw.get("vistos", []))[:MAX_REMEMBERED],
            last_run=raw.get("ultima_corrida"),
        )
    except (json.JSONDecodeError, OSError, TypeError) as exc:
        log.warning("Estado ilegible en %s (%s); se empieza de cero.", file, exc)
        return State()


def save(path: str | Path, articles: list[Article], previous: State) -> None:
    """Guarda los ids actuales al frente, conservando algo de historial."""
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)

    # Se guardan también los uids de las versiones fusionadas: así la historia
    # se reconoce aunque en la próxima corrida la represente otro medio.
    current = [uid for a in articles for uid in a.all_uids]
    merged: list[str] = []
    seen: set[str] = set()
    for uid in current + previous.seen:
        if uid not in seen:
            seen.add(uid)
            merged.append(uid)
        if len(merged) >= MAX_REMEMBERED:
            break

    payload = {
        "ultima_corrida": datetime.now(timezone.utc).isoformat(),
        "vistos": merged,
    }
    file.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def count_new(articles: list[Article], previous: State) -> int:
    """Cuántas historias no se habían visto en ninguna de sus versiones."""
    known = previous.seen_set
    return sum(1 for a in articles if not any(uid in known for uid in a.all_uids))
