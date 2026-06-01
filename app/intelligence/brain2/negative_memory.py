"""Negative outcome memory — survival-weighted cognition hierarchy."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from app.intelligence.brain2.memory_loader import SemanticMemoryStore


@dataclass
class NegativeMemoryInfluence:
    failure_match_count: int
    catastrophic_weight: float
    false_confidence_penalty: float
    replay_failure_boost: float
    survival_bias_applied: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("catastrophic_weight", "false_confidence_penalty", "replay_failure_boost"):
            d[k] = round(float(d[k]), 4)
        return d


def apply_negative_memory_priority(
    memory: SemanticMemoryStore,
    persistent: dict[str, Any],
    *,
    edge_strength: float,
    structure_confidence: float,
    semantic_confidence: float,
    exec_guards_ok: bool,
    replay_divergence_magnitude: float,
    active_behaviors: list[str],
) -> NegativeMemoryInfluence:
    matches = 0
    cat_weight = 0.0
    false_conf_penalty = 0.0
    replay_boost = 0.0

    behavior_set = set(active_behaviors)
    for fm in memory.failure_memories:
        triggers = [str(t).lower() for t in fm.get("trigger_pattern") or []]
        hit = 0
        for t in triggers:
            if "slippage" in t and "slippage_spike" in behavior_set:
                hit += 1
            elif "latency" in t and "latency_instability" in behavior_set:
                hit += 1
            elif "forced_urgency" in t and "urgency_dilemma" in behavior_set:
                hit += 1
            elif "edge_without_structure" in t and edge_strength > 0.35 and structure_confidence < 0.4:
                hit += 1
            elif "crowd_chase" in t and edge_strength > 0.4 and structure_confidence < 0.45:
                hit += 1
            elif "replay_signature_mismatch" in t and replay_divergence_magnitude >= 0.25:
                hit += 1
            elif "high_entropy" in t and "entropy_spike" in behavior_set:
                hit += 1
        if hit >= 2:
            matches += 1
            cat_weight = max(cat_weight, float(fm.get("semantic_weight", 0.7)))

    if edge_strength > 0.4 and structure_confidence < 0.45:
        false_conf_penalty = min(0.35, 0.15 + edge_strength * 0.25)

    if not exec_guards_ok:
        cat_weight = max(cat_weight, 0.82)
        false_conf_penalty = max(false_conf_penalty, 0.22)

    if replay_divergence_magnitude >= 0.35:
        replay_boost = min(0.4, replay_divergence_magnitude * 0.65)
        fid = "NEG_REPLAY_DRIFT_001"
        reinf = persistent.setdefault("failure_reinforcement", {})
        reinf[fid] = int(reinf.get(fid, 0)) + 1
        replay_boost += min(0.15, reinf[fid] * 0.03)

    survival = matches > 0 or cat_weight >= 0.75 or false_conf_penalty > 0.2

    return NegativeMemoryInfluence(
        failure_match_count=matches,
        catastrophic_weight=cat_weight,
        false_confidence_penalty=false_conf_penalty,
        replay_failure_boost=replay_boost,
        survival_bias_applied=survival,
    )


def adjust_confidence_for_survival(
    semantic_confidence: float,
    influence: NegativeMemoryInfluence,
) -> float:
    conf = semantic_confidence
    if influence.catastrophic_weight > 0:
        conf *= max(0.25, 1.0 - influence.catastrophic_weight * 0.55)
    conf -= influence.false_confidence_penalty
    conf *= max(0.35, 1.0 - influence.replay_failure_boost)
    return max(0.05, min(1.0, conf))
