"""Persistent replay storage — battlefield memory survives restart/session/regime."""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from loguru import logger

_REPLAY_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "brain2",
    "replay",
)
_MAX_HISTORY = 200


def _symbol_key(symbol: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", symbol.lower()).strip("_")


def _path(symbol: str) -> str:
    os.makedirs(_REPLAY_ROOT, exist_ok=True)
    return os.path.join(_REPLAY_ROOT, f"{_symbol_key(symbol)}.json")


def _empty_store(symbol: str) -> dict[str, Any]:
    return {"symbol": symbol, "latest": None, "history": []}


def _load_store(symbol: str) -> dict[str, Any]:
    path = _path(symbol)
    if not os.path.isfile(path):
        return _empty_store(symbol)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_store(symbol)
        data.setdefault("history", [])
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[ReplayEngine] load fail {symbol}: {exc}")
        return _empty_store(symbol)


def _save_store(symbol: str, store: dict[str, Any]) -> None:
    try:
        with open(_path(symbol), "w", encoding="utf-8") as f:
            json.dump(store, f, indent=2)
    except OSError as exc:
        logger.warning(f"[ReplayEngine] save fail {symbol}: {exc}")


def load_snapshot(symbol: str) -> dict[str, Any] | None:
    """Latest replay snapshot (backward compatible)."""
    store = _load_store(symbol)
    latest = store.get("latest")
    return latest if isinstance(latest, dict) else None


def load_replay_history(symbol: str, *, limit: int = 20) -> list[dict[str, Any]]:
    store = _load_store(symbol)
    hist = store.get("history") or []
    if not isinstance(hist, list):
        return []
    return [h for h in hist[-limit:] if isinstance(h, dict)]


def store_snapshot(symbol: str, payload: dict[str, Any]) -> None:
    """Persist snapshot with history ring buffer."""
    store = _load_store(symbol)
    entry = {
        **payload,
        "stored_at": int(time.time()),
    }
    store["latest"] = entry
    hist: list[dict[str, Any]] = list(store.get("history") or [])
    hist.append(entry)
    if len(hist) > _MAX_HISTORY:
        hist = _rank_and_trim_replay_history(hist, _MAX_HISTORY)
    store["history"] = hist
    store["symbol"] = symbol
    _save_store(symbol, store)


def append_replay_snapshot(symbol: str, payload: dict[str, Any]) -> None:
    """Alias for store_snapshot — explicit append semantics."""
    store_snapshot(symbol, payload)


def _rank_and_trim_replay_history(hist: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Keep high-relevance replay entries: divergence, failure, contra pressure."""
    if len(hist) <= cap:
        return hist

    def _score(item: dict[str, Any]) -> float:
        return (
            float(item.get("divergence_magnitude") or 0) * 0.35
            + float(item.get("accumulated_contradiction_pressure") or 0) * 0.25
            + (0.2 if item.get("execution_guards_ok") is False else 0.0)
            + float(item.get("impact_stress") or 0) * 0.15
            + (0.05 if item.get("mutation_drift") else 0.0)
        )

    ranked = sorted(hist, key=_score, reverse=True)
    keep_top = ranked[: max(1, cap // 4)]
    recent = hist[-(cap - len(keep_top)) :]
    merged: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for item in keep_top + recent:
        key = str(item.get("bar_index", item.get("stored_at", id(item))))
        if key in seen_ids:
            continue
        seen_ids.add(key)
        merged.append(item)
    merged.sort(key=lambda x: int(x.get("stored_at") or 0))
    return merged[-cap:]
