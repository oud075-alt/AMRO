"""Causal confidence layer — separate observed vs inferred vs speculative semantics."""
from __future__ import annotations

from app.intelligence.brain2.models import SemanticInterpretation

CAUSAL_OBSERVED = 1
CAUSAL_STRUCTURAL = 2
CAUSAL_SEMANTIC = 3
CAUSAL_SPECULATIVE = 4

# Level 1 — direct runtime measurements / guard failures
_LEVEL1: set[str] = {
    "spread_widening",
    "volume_thinning",
    "latency_instability",
    "signed_order_flow_pressure",
}

# Level 2 — structural inference from telemetry
_LEVEL2: set[str] = {
    "liquidity_thinning",
    "volatility_expansion",
    "entropy_spike",
    "continuation_degrading",
    "distribution_shift",
    "weak_edge_environment",
    "size_pressure",
    "informed_trading_presence",
}

# Level 3 — semantic behavioral interpretation (governance-eligible with decay)
_LEVEL3: set[str] = {
    "breakout_without_continuation",
    "trap_probability",
    "adverse_selection_cost",
    "illiquidity_premium_risk",
    "execution_fragility",
    "instability_risk",
    "unstable_continuation",
    "panic_acceleration",
    "limits_to_arbitrage",
    "urgency_dilemma",
    "delay_cost_escalation",
    "market_impact_nonlinearity",
    "absorption_or_exhaustion",
    "participation_unreliable",
    "continuation_fragility",
}

# Level 4 — speculative narrative — NEVER direct governance influence
_LEVEL4: set[str] = {
    "narrative_drift",
    "synthetic_similarity",
    "regime_mutation",
    "implementation_shortfall",
    "semantic_confidence_collapse",
    "contradiction_accumulation",
    "market_noise",
    "noise_trader_sentiment_shift",
}


def classify_causal_level(behavior: str, evidence: list[str], *, propagated: bool = False) -> int:
    b = behavior.lower()
    if any("execution_guard" in e for e in evidence):
        return CAUSAL_OBSERVED
    if b in _LEVEL1:
        return CAUSAL_OBSERVED
    if b in _LEVEL2:
        return CAUSAL_STRUCTURAL
    if b in _LEVEL3:
        return CAUSAL_SEMANTIC
    if b in _LEVEL4:
        return CAUSAL_SPECULATIVE
    if propagated:
        return CAUSAL_SEMANTIC
    if any(k in b for k in ("trap", "fake", "panic", "fragil")):
        return CAUSAL_SEMANTIC
    if any(k in b for k in ("narrative", "drift", "mutation", "noise", "synthetic")):
        return CAUSAL_SPECULATIVE
    return CAUSAL_STRUCTURAL


def apply_causal_layer(
    interpretations: list[SemanticInterpretation],
) -> list[SemanticInterpretation]:
    out: list[SemanticInterpretation] = []
    for item in interpretations:
        propagated = any("relation:" in e for e in item.evidence)
        level = classify_causal_level(item.behavior, item.evidence, propagated=propagated)
        if propagated and level < CAUSAL_SEMANTIC:
            level = min(CAUSAL_SPECULATIVE, level + 1)
        eligible = level <= CAUSAL_SEMANTIC
        conf = item.confidence
        if level == CAUSAL_SPECULATIVE:
            conf *= 0.35
        elif level == CAUSAL_SEMANTIC:
            conf *= 0.85
        out.append(SemanticInterpretation(
            behavior=item.behavior,
            meaning=item.meaning,
            confidence=round(conf, 4),
            evidence=item.evidence + [f"causal_level={level}"],
            regime=item.regime,
            decay=item.decay,
            causal_level=level,
            governance_eligible=eligible,
            memory_sources=list(item.memory_sources),
            memory_support=item.memory_support,
            contradiction_status=item.contradiction_status,
            replay_trust=item.replay_trust,
            execution_survivability=item.execution_survivability,
            regime_alignment=item.regime_alignment,
            uncertainty_level=item.uncertainty_level,
        ))
    return out


def aggregate_governance_confidence(interpretations: list[SemanticInterpretation]) -> float:
    """Levels 1–3 only — Level 4 excluded from governance influence."""
    eligible = [i for i in interpretations if getattr(i, "governance_eligible", True) and getattr(i, "causal_level", 3) <= CAUSAL_SEMANTIC]
    if not eligible:
        return 0.0
    weights = {CAUSAL_OBSERVED: 1.0, CAUSAL_STRUCTURAL: 0.85, CAUSAL_SEMANTIC: 0.65}
    total_w = 0.0
    total = 0.0
    for item in eligible[:6]:
        lvl = getattr(item, "causal_level", CAUSAL_SEMANTIC)
        w = weights.get(lvl, 0.5)
        total += item.confidence * w
        total_w += w
    return round(total / max(total_w, 1e-9), 4)


def aggregate_full_semantic_confidence(interpretations: list[SemanticInterpretation]) -> float:
    """All levels — L4 heavily discounted (audit only)."""
    if not interpretations:
        return 0.0
    total = 0.0
    for item in interpretations[:8]:
        lvl = getattr(item, "causal_level", 3)
        discount = 1.0 if lvl <= CAUSAL_SEMANTIC else 0.2
        total += item.confidence * discount
    return round(total / min(8, len(interpretations)), 4)
