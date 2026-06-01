"""Contextual sequence memory — persisted across restarts."""
from __future__ import annotations

from typing import Any

from app.intelligence.brain2.models import SequencePhase
from app.intelligence.brain2.persistent_store import load_persistent_state, save_persistent_state


def _classify_phase(
    *,
    instability: float,
    entropy: float,
    structure_confidence: float,
    edge_strength: float,
    market_state: str,
) -> tuple[str, str, float]:
    if market_state == "chaotic":
        return "climax", "panic", 0.78
    if instability > 0.72 and entropy > 0.65:
        return "climax", "panic_acceleration", 0.74
    if edge_strength > 0.5 and structure_confidence > 0.5:
        return "transition", "aggression", 0.62
    if structure_confidence < 0.35 and edge_strength > 0.3:
        return "aftermath", "exhaustion", 0.58
    if structure_confidence < 0.45 and instability < 0.5:
        return "before", "hesitation", 0.55
    if instability > 0.55:
        return "transition", "instability_build", 0.60
    return "before", "neutral_observation", 0.40


def update_sequence_memory(
    symbol: str,
    *,
    bar_index: int,
    regime: str,
    instability: float,
    entropy: float,
    structure_confidence: float,
    edge_strength: float,
    market_state: str,
    persistent: dict[str, Any] | None = None,
    max_len: int = 24,
) -> list[SequencePhase]:
    state = persistent if persistent is not None else load_persistent_state(symbol)
    phase, behavior, conf = _classify_phase(
        instability=instability,
        entropy=entropy,
        structure_confidence=structure_confidence,
        edge_strength=edge_strength,
        market_state=market_state,
    )
    key = f"{phase}:{behavior}"
    log: list[dict[str, Any]] = list(state.get("sequence_log") or [])
    if not log or log[-1].get("key") != key:
        log.append({
            "bar": bar_index,
            "regime": regime,
            "key": key,
            "phase": phase,
            "behavior": behavior,
            "confidence": conf,
        })
    if len(log) > max_len:
        log = log[-max_len:]
    state["sequence_log"] = log
    state["bar_count"] = bar_index
    state["last_regime"] = regime
    if persistent is None:
        save_persistent_state(symbol, state)

    phases: list[SequencePhase] = []
    for item in log[-6:]:
        phases.append(SequencePhase(
            phase=str(item.get("phase", "before")),
            behavior=str(item.get("behavior", "neutral")),
            confidence=float(item.get("confidence", 0.45)),
        ))
    return phases
