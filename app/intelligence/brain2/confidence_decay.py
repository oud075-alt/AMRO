"""Confidence decay for semantic interpretations — no permanent truth."""
from __future__ import annotations

from app.intelligence.brain2.models import SemanticInterpretation


def apply_confidence_decay(
    interpretations: list[SemanticInterpretation],
    *,
    bar_age: int = 0,
    contradiction_count: int = 0,
    replay_supported: bool = False,
    replay_divergence_magnitude: float = 0.0,
    accumulated_contradiction_pressure: float = 0.0,
    cognitive_overload: bool = False,
) -> list[SemanticInterpretation]:
    out: list[SemanticInterpretation] = []
    age_factor = max(0.35, 1.0 - bar_age * 0.02)
    contra_factor = max(0.2, 1.0 - contradiction_count * 0.1 - accumulated_contradiction_pressure * 0.35)
    replay_factor = 1.05 if replay_supported and replay_divergence_magnitude < 0.12 else 1.0
    if replay_divergence_magnitude >= 0.15:
        replay_factor *= max(0.4, 1.0 - replay_divergence_magnitude * 0.75)
    overload_factor = 0.75 if cognitive_overload else 1.0

    for item in interpretations:
        decay = min(1.0, age_factor * contra_factor * replay_factor * overload_factor * item.decay)
        conf = item.confidence * decay
        out.append(SemanticInterpretation(
            behavior=item.behavior,
            meaning=item.meaning,
            confidence=round(conf, 4),
            evidence=item.evidence,
            regime=item.regime,
            decay=round(decay, 4),
            causal_level=getattr(item, "causal_level", 2),
            governance_eligible=getattr(item, "governance_eligible", True),
            memory_sources=list(getattr(item, "memory_sources", [])),
            memory_support=getattr(item, "memory_support", 0.0),
            contradiction_status=getattr(item, "contradiction_status", "clear"),
            replay_trust=getattr(item, "replay_trust", 0.5),
            execution_survivability=getattr(item, "execution_survivability", "unknown"),
            regime_alignment=getattr(item, "regime_alignment", "neutral"),
            uncertainty_level=getattr(item, "uncertainty_level", "moderate"),
        ))
    return out


def aggregate_semantic_confidence(interpretations: list[SemanticInterpretation]) -> float:
    if not interpretations:
        return 0.0
    return round(sum(i.confidence for i in interpretations[:5]) / min(5, len(interpretations)), 4)
