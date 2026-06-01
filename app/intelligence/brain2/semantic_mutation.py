"""Semantic mutation tracker — behaviors change meaning over time."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


MUTATION_RULES: dict[str, dict[str, str]] = {
    "breakout_without_continuation": {
        "stable": "breakout continuation candidate",
        "degraded": "crowded breakout trap risk",
        "contradicted": "false breakout — absorption likely",
    },
    "continuation_degrading": {
        "stable": "continuation monitoring",
        "degraded": "continuation decay — unstable trend",
        "contradicted": "trend exhaustion — reversal pressure",
    },
    "volatility_expansion": {
        "stable": "volatility expansion",
        "degraded": "panic acceleration zone",
        "contradicted": "liquidity vacuum — forced deleveraging",
    },
}


@dataclass
class SemanticMutationState:
    drift_score: float
    mutations: list[dict[str, Any]]
    edge_degradation: float
    continuation_decay: float
    contradiction_recurrence: float

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("drift_score", "edge_degradation", "continuation_decay", "contradiction_recurrence"):
            d[k] = round(float(d[k]), 4)
        return d


def track_semantic_mutations(
    persistent: dict[str, Any],
    *,
    bar_index: int,
    regime: str,
    active_behaviors: list[tuple[str, float, list[str]]],
    structure_confidence: float,
    edge_strength: float,
    contradiction_recurrence: float,
    continuation_probability: float,
) -> SemanticMutationState:
    log: list[dict[str, Any]] = list(persistent.get("semantic_mutations") or [])
    mutations: list[dict[str, Any]] = []

    edge_deg = max(0.0, min(1.0, (0.55 - structure_confidence) * 0.8 + (0.5 - edge_strength) * 0.3))
    cont_decay = max(0.0, min(1.0, 0.65 - continuation_probability))

    for behavior, activation, _ in active_behaviors:
        rules = MUTATION_RULES.get(behavior)
        if not rules:
            continue

        if contradiction_recurrence >= 0.35 and activation >= 0.5:
            phase = "contradicted"
        elif edge_deg >= 0.35 or cont_decay >= 0.35:
            phase = "degraded"
        else:
            phase = "stable"

        meaning = rules[phase]
        entry = {
            "bar": bar_index,
            "regime": regime,
            "behavior": behavior,
            "phase": phase,
            "meaning": meaning,
            "activation": round(activation, 4),
        }
        log.append(entry)
        if phase != "stable":
            mutations.append(entry)

    if len(log) > 80:
        log = log[-80:]
    persistent["semantic_mutations"] = log

    drift_score = min(
        1.0,
        len(mutations) * 0.12 + edge_deg * 0.35 + cont_decay * 0.25 + contradiction_recurrence * 0.28,
    )

    return SemanticMutationState(
        drift_score=drift_score,
        mutations=mutations[-5:],
        edge_degradation=edge_deg,
        continuation_decay=cont_decay,
        contradiction_recurrence=contradiction_recurrence,
    )
