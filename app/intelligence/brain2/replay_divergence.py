"""Replay/live divergence magnitude — not bool-only illusion."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.intelligence.brain2.microstructure_grounding import MicrostructureGrounding, impact_telemetry_penalty


@dataclass
class ReplayDivergenceMetrics:
    signature_mismatch: bool
    fill_delta: float
    spread_delta: float
    execution_delay_delta: float
    continuation_delta: float
    semantic_delta: float
    impact_delta: float
    divergence_magnitude: float
    cumulative_divergence: float
    replay_reliability: float
    distrust_level: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in (
            "fill_delta", "spread_delta", "execution_delay_delta", "continuation_delta",
            "semantic_delta", "impact_delta", "divergence_magnitude", "cumulative_divergence",
            "replay_reliability",
        ):
            d[k] = round(float(d[k]), 4)
        return d


def compute_replay_divergence(
    prior: dict[str, Any] | None,
    *,
    micro: MicrostructureGrounding,
    structure_confidence: float,
    semantic_confidence: float,
    continuation_probability: float,
    execution_health: float,
    replay_signature: str,
    replay_history: list[dict[str, Any]] | None = None,
) -> ReplayDivergenceMetrics:
    if not prior:
        return ReplayDivergenceMetrics(
            signature_mismatch=False,
            fill_delta=0.0,
            spread_delta=0.0,
            execution_delay_delta=0.0,
            continuation_delta=0.0,
            semantic_delta=0.0,
            impact_delta=0.0,
            divergence_magnitude=0.0,
            cumulative_divergence=0.0,
            replay_reliability=0.5,
            distrust_level="unknown",
        )

    sig_mismatch = bool(
        replay_signature
        and prior.get("replay_signature")
        and prior.get("replay_signature") != replay_signature
    )

    prior_fill = float(prior.get("fill_vol_ratio", 1.0))
    prior_spread = float(prior.get("spread_proxy", micro.spread_proxy))
    prior_exec = float(prior.get("execution_health", execution_health))
    prior_struct = float(prior.get("structure_confidence", structure_confidence))
    prior_sem = float(prior.get("semantic_confidence", semantic_confidence))
    prior_cont = float(prior.get("continuation_probability", continuation_probability))
    prior_impact = float(prior.get("impact_stress", micro.impact_stress))

    fill_delta = abs(micro.fill_vol_ratio - prior_fill)
    spread_delta = abs(micro.spread_proxy - prior_spread) / max(prior_spread, 1e-8)
    exec_delta = abs(execution_health - prior_exec)
    cont_delta = abs(continuation_probability - prior_cont)
    sem_delta = abs(semantic_confidence - prior_sem)
    struct_delta = abs(structure_confidence - prior_struct)
    impact_delta = abs(micro.impact_stress - prior_impact)

    impact_pen = impact_telemetry_penalty(micro)

    magnitude = min(
        1.0,
        fill_delta * 0.22
        + min(1.0, spread_delta) * 0.18
        + exec_delta * 0.12
        + cont_delta * 0.12
        + sem_delta * 0.12
        + struct_delta * 0.08
        + impact_delta * 0.14
        + impact_pen * 0.12
        + (0.12 if sig_mismatch else 0.0),
    )

    cumulative = magnitude
    if replay_history and len(replay_history) >= 2:
        prior_divs = [float(h.get("divergence_magnitude") or 0) for h in replay_history[-5:]]
        cumulative = min(1.0, magnitude * 0.55 + sum(prior_divs) / len(prior_divs) * 0.45)

    reliability = max(0.05, 1.0 - cumulative)
    distrust_val = max(magnitude, cumulative * 0.85)
    if distrust_val >= 0.55:
        distrust = "high"
    elif distrust_val >= 0.28:
        distrust = "elevated"
    elif distrust_val >= 0.12:
        distrust = "moderate"
    else:
        distrust = "low"

    return ReplayDivergenceMetrics(
        signature_mismatch=sig_mismatch,
        fill_delta=fill_delta,
        spread_delta=spread_delta,
        execution_delay_delta=exec_delta,
        continuation_delta=cont_delta,
        semantic_delta=sem_delta,
        impact_delta=impact_delta,
        divergence_magnitude=magnitude,
        cumulative_divergence=cumulative,
        replay_reliability=reliability,
        distrust_level=distrust,
    )
