from __future__ import annotations

import json
import os
from pathlib import Path

from models import SyncPair

_FILENAME = "sync_pairs.json"


def _store_path() -> Path:
    if os.environ.get("BISYNC_DATA"):
        return Path(os.environ["BISYNC_DATA"])
    try:
        from android.storage import app_storage_path

        return Path(app_storage_path())
    except ImportError:
        return Path.home() / ".bisync"


def _json_path() -> Path:
    p = _store_path() / _FILENAME
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_pairs() -> list[SyncPair]:
    p = _json_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text())
        return [SyncPair.from_dict(d) for d in data]
    except (json.JSONDecodeError, KeyError):
        return []


def save_pairs(pairs: list[SyncPair]) -> None:
    p = _json_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps([pair.to_dict() for pair in pairs], indent=2))


def add_pair(pair: SyncPair) -> None:
    pairs = load_pairs()
    pairs.append(pair)
    save_pairs(pairs)


def update_pair(pair: SyncPair) -> None:
    pairs = load_pairs()
    for i, p in enumerate(pairs):
        if p.id == pair.id:
            pairs[i] = pair
            break
    save_pairs(pairs)


def delete_pair(pair_id: str) -> None:
    pairs = load_pairs()
    pairs = [p for p in pairs if p.id != pair_id]
    save_pairs(pairs)


def get_pair(pair_id: str) -> SyncPair | None:
    for p in load_pairs():
        if p.id == pair_id:
            return p
    return None
