"""Runtime cognitive health — Brain-2 monitors its own cognition load."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.intelligence.brain2.models import SemanticInterpretation


@dataclass
class CognitiveHealthState:
    overload: bool
    contradiction_saturation: float
    semantic_instability: float
    overinterpretation_risk: float
    narrative_recursion_pressure: float
    health_level: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("contradiction_saturation", "semantic_instability", "overinterpretation_risk",
                  "narrative_recursion_pressure"):
            d[k] = round(float(d[k]), 4)
        return d


def evaluate_cognitive_health(
    *,
    interpretations: list[SemanticInterpretation],
    contradiction_pressure: float,
    accumulated_contradiction_pressure: float,
    synthetic_similarity: float,
    semantic_confidence: float,
) -> CognitiveHealthState:
    n_interp = len(interpretations)
    confs = [i.confidence for i in interpretations[:8]]
    if len(confs) >= 2:
        mean_c = sum(confs) / len(confs)
        var_c = sum((c - mean_c) ** 2 for c in confs) / len(confs)
        semantic_instability = min(1.0, var_c * 4.0 + (1.0 - semantic_confidence) * 0.35)
    else:
        semantic_instability = max(0.0, 0.4 - semantic_confidence)

    contra_sat = min(1.0, contradiction_pressure * 0.5 + accumulated_contradiction_pressure * 0.5)
    overinterp = min(1.0, max(0.0, (n_interp - 5) * 0.12))
    narrative_rec = min(1.0, synthetic_similarity * 0.55 + overinterp * 0.35)

    overload = (
        contra_sat >= 0.62
        or (overinterp >= 0.45 and narrative_rec >= 0.5)
        or semantic_instability >= 0.65
    )

    if overload or contra_sat >= 0.72:
        level = "critical"
    elif contra_sat >= 0.45 or narrative_rec >= 0.55:
        level = "strained"
    elif contra_sat >= 0.25:
        level = "watch"
    else:
        level = "stable"

    return CognitiveHealthState(
        overload=overload,
        contradiction_saturation=contra_sat,
        semantic_instability=semantic_instability,
        overinterpretation_risk=overinterp,
        narrative_recursion_pressure=narrative_rec,
        health_level=level,
    )
