"""Persistent Brain-2 state — survives restarts (contradictions, sequences, mutations)."""
from __future__ import annotations

import json
import os
import re
from typing import Any

from loguru import logger

_STATE_ROOT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "brain2",
    "state",
)


def _symbol_key(symbol: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", symbol.lower()).strip("_")


def _path(symbol: str) -> str:
    os.makedirs(_STATE_ROOT, exist_ok=True)
    return os.path.join(_STATE_ROOT, f"{_symbol_key(symbol)}.json")


def load_persistent_state(symbol: str) -> dict[str, Any]:
    path = _path(symbol)
    if not os.path.isfile(path):
        return _empty_state(symbol)
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return _empty_state(symbol)
        return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning(f"[Brain2Store] load fail {symbol}: {exc}")
        return _empty_state(symbol)


def save_persistent_state(symbol: str, state: dict[str, Any]) -> None:
    path = _path(symbol)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except OSError as exc:
        logger.warning(f"[Brain2Store] save fail {symbol}: {exc}")


def _empty_state(symbol: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "bar_count": 0,
        "last_regime": "",
        "contradiction_log": [],
        "sequence_log": [],
        "semantic_mutations": [],
        "failure_reinforcement": {},
        "last_snapshot": {},
    }
