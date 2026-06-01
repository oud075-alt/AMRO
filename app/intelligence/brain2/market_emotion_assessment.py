"""
Probabilistic market emotion assessment — advisory only, never ground truth.

Maps observable runtime telemetry to emotion probabilities using ingested
AMRO_Market_Vision_KB rules. No certainty output allowed.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from app.intelligence.brain2.microstructure_grounding import MicrostructureGrounding
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState

_RULES_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
    "data",
    "brain2",
    "packs",
    "AMRO_Market_Vision_KB_v1",
    "emotion_runtime_rules.json",
)


@dataclass
class MarketEmotionState:
    fear: float
    greed: float
    panic: float
    hesitation: float
    exhaustion: float
    aggression: float
    primary_emotion: str
    primary_emotion_th: str
    primary_probability: float
    secondary_emotion: str
    secondary_probability: float
    period_risk_score: float
    period_risk_level: str
    mood_summary_th: str
    uncertainty: str
    evidence: list[str]
    policy: str = "probabilistic_emotion_v1"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in (
            "fear", "greed", "panic", "hesitation", "exhaustion", "aggression",
            "primary_probability", "secondary_probability", "period_risk_score",
        ):
            d[k] = round(float(d[k]), 4)
        return d


def _load_rules() -> list[dict[str, Any]]:
    try:
        with open(_RULES_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _clip(v: float) -> float:
    return float(np.clip(v, 0.0, 1.0))


def _risk_level(score: float) -> str:
    if score >= 0.72:
        return "elevated"
    if score >= 0.48:
        return "moderate"
    if score >= 0.28:
        return "watch"
    return "low"


def _soft_match(value: float, threshold: float, *, above: bool = True) -> float:
    if above:
        if value >= threshold:
            return _clip(0.55 + (value - threshold) * 1.2)
        return _clip(value / max(threshold, 1e-6) * 0.45)
    if value <= threshold:
        return _clip(0.55 + (threshold - value) * 1.2)
    return _clip((1.0 - value) / max(1.0 - threshold, 1e-6) * 0.45)


def assess_market_emotion(
    market: MarketStructureState,
    *,
    micro: MicrostructureGrounding,
    continuation_p: float,
    exhaustion_p: float,
    instability_p: float,
    fakeout_p: float,
    crowd_pressure: float = 0.0,
    panic_acceleration: float = 0.0,
    edge_strength: float = 0.0,
    drawdown: float = 0.0,
    exec_fragility: float = 0.0,
    mutation_drift: float = 0.0,
    governance_confidence: float = 0.5,
    abstention_tendency: float = 0.0,
) -> MarketEmotionState:
    """Compute emotion probabilities from observable state — not predictive certainty."""
    sc = market.structure_confidence
    inst = market.instability_score
    ent = market.entropy_score
    synth = market.synthetic_similarity
    shift = market.distribution_shift
    impact = micro.impact_stress
    signed = abs(micro.signed_pressure)
    vol_asym = micro.volume_return_asymmetry
    compression = _clip(1.0 - inst * 0.6 - abs(continuation_p - 0.5) * 0.8)
    low_pullback = _clip(continuation_p * (1.0 - fakeout_p * 0.5))

    features = {
        "instability": inst,
        "entropy": ent,
        "impact_stress": impact,
        "low_structure": _clip(1.0 - sc),
        "continuation": continuation_p,
        "crowd_pressure": crowd_pressure,
        "edge_strength": edge_strength,
        "low_pullback_proxy": low_pullback,
        "drawdown": drawdown,
        "exec_fragility": exec_fragility,
        "panic_acceleration": panic_acceleration,
        "compression_proxy": compression,
        "low_continuation": _clip(1.0 - continuation_p),
        "moderate_entropy": _clip(1.0 - abs(ent - 0.5) * 2),
        "exhaustion_probability": exhaustion_p,
        "mutation_drift": mutation_drift,
        "signed_pressure": signed,
        "distribution_shift": shift,
        "vol_asymmetry": vol_asym,
    }

    scores: dict[str, float] = {}
    evidence: list[str] = []

    fear = _clip(
        inst * 0.35 + ent * 0.25 + impact * 0.25 + (1.0 - sc) * 0.15
    )
    greed = _clip(
        continuation_p * 0.35 + crowd_pressure * 0.3 + edge_strength * 0.2 + low_pullback * 0.15
    )
    if synth > 0.65:
        greed *= max(0.35, 1.0 - (synth - 0.65) * 1.5)

    panic = _clip(
        inst * 0.3 + impact * 0.25 + drawdown * 0.2 + panic_acceleration * 0.25 + exec_fragility * 0.15
    )
    hesitation = _clip(
        compression * 0.4 + (1.0 - continuation_p) * 0.35 + _clip(1.0 - abs(ent - 0.5) * 2) * 0.25
    )
    exhaustion = _clip(exhaustion_p * 0.45 + (1.0 - sc) * 0.25 + mutation_drift * 0.3)
    aggression = _clip(
        signed * 0.35 + inst * 0.25 + shift * 0.2 + vol_asym * 0.2
    )

    scores = {
        "fear": fear,
        "greed": greed,
        "panic": panic,
        "hesitation": hesitation,
        "exhaustion": exhaustion,
        "aggression": aggression,
    }

    if inst >= 0.45:
        evidence.append(f"instability={inst:.2f}")
    if ent >= 0.45:
        evidence.append(f"entropy={ent:.2f}")
    if impact >= 0.2:
        evidence.append(f"impact_stress={impact:.2f}")
    if crowd_pressure >= 0.3:
        evidence.append(f"crowd_pressure={crowd_pressure:.2f}")
    if drawdown >= 0.06:
        evidence.append(f"drawdown={drawdown:.2f}")
    if signed >= 0.3:
        evidence.append(f"signed_pressure={signed:.2f}")

    rules = _load_rules()
    label_th = {r["emotion_id"]: r.get("label_th", r["emotion_id"]) for r in rules}

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    primary_id, primary_p = ranked[0]
    secondary_id, secondary_p = ranked[1] if len(ranked) > 1 else ("hesitation", 0.0)

    period_risk = _clip(
        max(instability_p, inst) * 0.35
        + impact * 0.2
        + panic * 0.25
        + (1.0 - governance_confidence) * 0.2
        + abstention_tendency * 0.15
    )
    risk_level = _risk_level(period_risk)

    primary_th = label_th.get(primary_id, primary_id)
    secondary_th = label_th.get(secondary_id, secondary_id)

    if primary_p < 0.28:
        mood = (
            f"อารมณ์ตลาดไม่ชัด — ส mix หลายแบบ; "
            f"dominant ~{primary_th} {primary_p:.0%} (ไม่ฟันธง)"
        )
    else:
        mood = (
            f"โอกาสสูงสุด ~{primary_th} {primary_p:.0%}; "
            f"รอง ~{secondary_th} {secondary_p:.0%} — ประเมินความเสี่ยงช่วงนี้={risk_level}"
        )

    uncertainty = (
        "probabilistic emotion only — not ground truth — "
        "memory-first policy; abstain when confidence low"
    )
    if primary_p < 0.35:
        uncertainty += " — emotion signal weak"
    if synth > 0.7:
        uncertainty += " — synthetic noise may distort emotion read"
    if abstention_tendency >= 0.35:
        uncertainty += f" — abstention={abstention_tendency:.2f}"

    return MarketEmotionState(
        fear=scores["fear"],
        greed=scores["greed"],
        panic=scores["panic"],
        hesitation=scores["hesitation"],
        exhaustion=scores["exhaustion"],
        aggression=scores["aggression"],
        primary_emotion=primary_id,
        primary_emotion_th=primary_th,
        primary_probability=primary_p,
        secondary_emotion=secondary_id,
        secondary_probability=secondary_p,
        period_risk_score=period_risk,
        period_risk_level=risk_level,
        mood_summary_th=mood,
        uncertainty=uncertainty,
        evidence=evidence[:8],
    )
