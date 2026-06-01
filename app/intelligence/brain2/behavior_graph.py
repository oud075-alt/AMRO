"""Behavioral relation graph — weighted relations with regime dependency."""
from __future__ import annotations

from typing import Any

from app.intelligence.brain2.memory_loader import SemanticMemoryStore
from app.intelligence.brain2.microstructure_grounding import MicrostructureGrounding

# Core runtime relations (always present)
BEHAVIOR_RELATIONS: list[dict[str, Any]] = [
    {"from": "liquidity_thinning", "to": "execution_fragility", "weight": 0.82, "regimes": ["*"]},
    {"from": "liquidity_thinning", "to": "continuation_fragility", "weight": 0.71, "regimes": ["RANGING", "TRANSITIONAL"]},
    {"from": "volatility_expansion", "to": "panic_acceleration", "weight": 0.68, "regimes": ["VOLATILE", "TRANSITIONAL"]},
    {"from": "volatility_expansion", "to": "instability_risk", "weight": 0.74, "regimes": ["*"]},
    {"from": "spread_widening", "to": "execution_fragility", "weight": 0.79, "regimes": ["*"]},
    {"from": "breakout_without_continuation", "to": "trap_probability", "weight": 0.76, "regimes": ["RANGING", "BREAKOUT"]},
    {"from": "repeated_rejection", "to": "absorption_or_exhaustion", "weight": 0.63, "regimes": ["*"]},
    {"from": "continuation_degrading", "to": "unstable_continuation", "weight": 0.70, "regimes": ["TRENDING_UP", "TRENDING_DOWN"]},
    {"from": "entropy_spike", "to": "market_noise", "weight": 0.77, "regimes": ["*"]},
    {"from": "synthetic_similarity", "to": "narrative_drift", "weight": 0.65, "regimes": ["*"]},
    {"from": "weak_edge_environment", "to": "participation_unreliable", "weight": 0.72, "regimes": ["*"]},
    {"from": "distribution_shift", "to": "regime_mutation", "weight": 0.69, "regimes": ["*"]},
    {"from": "volume_thinning", "to": "illiquidity_premium_risk", "weight": 0.78, "regimes": ["*"]},
    {"from": "signed_order_flow_pressure", "to": "adverse_selection_cost", "weight": 0.84, "regimes": ["*"]},
    {"from": "urgency_dilemma", "to": "implementation_shortfall", "weight": 0.88, "regimes": ["*"]},
    {"from": "latency_instability", "to": "delay_cost_escalation", "weight": 0.76, "regimes": ["*"]},
    {"from": "noise_trader_sentiment_shift", "to": "limits_to_arbitrage", "weight": 0.77, "regimes": ["*"]},
    {"from": "contradiction_accumulation", "to": "semantic_confidence_collapse", "weight": 0.80, "regimes": ["*"]},
]

SEMANTIC_TRANSLATIONS: dict[str, str] = {
    "liquidity_thinning": "Execution fragility elevated",
    "volatility_expansion": "Instability risk expanding",
    "spread_widening": "Execution cost instability",
    "breakout_without_continuation": "Trap probability elevated",
    "repeated_rejection": "Absorption or exhaustion pressure",
    "continuation_degrading": "Unstable continuation",
    "entropy_spike": "Market noise above tolerance",
    "synthetic_similarity": "Synthetic noise degrading trust",
    "weak_edge_environment": "Participation environment unreliable",
    "distribution_shift": "Regime mutation detected",
    "panic_acceleration": "Panic acceleration risk",
    "execution_fragility": "Execution fragility",
    "instability_risk": "Instability risk",
    "volume_thinning": "Fill quality degradation — illiquidity rising",
    "signed_order_flow_pressure": "Adverse selection cost rising",
    "adverse_selection_cost": "Informed flow may front-run visible signals",
    "illiquidity_premium_risk": "Price impact per unit volume elevated",
    "urgency_dilemma": "Speed vs impact tradeoff active",
    "implementation_shortfall": "Paper-to-live execution drag dominates",
    "latency_instability": "Decision-to-fill drift risk",
    "delay_cost_escalation": "Benchmark drift while unfilled",
    "size_pressure": "Non-linear market impact risk",
    "market_impact_nonlinearity": "Large participation moves price against self",
    "noise_trader_sentiment_shift": "Sentiment-driven flow uncoupled from structure",
    "limits_to_arbitrage": "Mispricing may widen before correction",
    "contradiction_accumulation": "Conflicting semantics accumulating",
    "semantic_confidence_collapse": "Interpretation reliability decaying",
    "informed_trading_presence": "Market maker adverse selection elevated",
}


def merged_relations(memory: SemanticMemoryStore | None = None) -> list[dict[str, Any]]:
    """Merge hardcoded graph with ingested pack relations."""
    out = list(BEHAVIOR_RELATIONS)
    seen = {(r["from"], r["to"]) for r in out}
    if memory:
        for row in memory.relations:
            src = row.get("from_behavior") or row.get("from")
            tgt = row.get("to_behavior") or row.get("to")
            if not src or not tgt:
                continue
            key = (str(src), str(tgt))
            if key in seen:
                continue
            out.append({
                "from": str(src),
                "to": str(tgt),
                "weight": float(row.get("weight", 0.65)),
                "regimes": row.get("regimes") or ["*"],
                "source": row.get("source", ""),
                "uncertainty": float(row.get("uncertainty", 0.4)),
            })
            seen.add(key)
    return out


def active_behaviors(
    *,
    instability: float,
    entropy: float,
    distribution_shift: float,
    synthetic_similarity: float,
    structure_confidence: float,
    environment_quality: float,
    edge_strength: float,
    market_state: str,
    slip_ok: bool = True,
    spread_ok: bool = True,
    fill_ok: bool = True,
    lat_ok: bool = True,
    execution_health: float = 1.0,
    replay_mismatch: bool = False,
    micro: MicrostructureGrounding | None = None,
    crowd_pressure: float = 0.0,
) -> list[tuple[str, float, list[str]]]:
    """Return (behavior_key, activation, evidence_lines) from runtime telemetry."""
    out: list[tuple[str, float, list[str]]] = []

    if instability >= 0.55:
        out.append(("volatility_expansion", min(1.0, instability), [f"instability={instability:.2f}"]))
    if entropy >= 0.55:
        out.append(("entropy_spike", min(1.0, entropy), [f"entropy={entropy:.2f}"]))
    if entropy >= 0.6 and synthetic_similarity >= 0.55:
        out.append(("noise_trader_sentiment_shift", min(1.0, (entropy + synthetic_similarity) / 2), [
            f"entropy={entropy:.2f}",
            f"synthetic_similarity={synthetic_similarity:.2f}",
        ]))
    if distribution_shift >= 0.45:
        out.append(("distribution_shift", min(1.0, distribution_shift), [f"distribution_shift={distribution_shift:.2f}"]))
    if synthetic_similarity >= 0.55:
        out.append(("synthetic_similarity", min(1.0, synthetic_similarity), [f"synthetic_similarity={synthetic_similarity:.2f}"]))
    if environment_quality < 0.40:
        out.append(("weak_edge_environment", 1.0 - environment_quality, [f"edge_environment={environment_quality:.2f}"]))
    if structure_confidence < 0.45 and edge_strength > 0.35:
        out.append(("breakout_without_continuation", 0.5 + (0.45 - structure_confidence), [
            f"structure_confidence={structure_confidence:.2f}",
            f"edge_strength={edge_strength:.2f}",
        ]))
    if market_state in ("unstable", "chaotic"):
        out.append(("liquidity_thinning", 0.55 + instability * 0.3, [f"market_state={market_state}"]))
    if structure_confidence < 0.35:
        out.append(("continuation_degrading", 0.6, [f"structure_confidence={structure_confidence:.2f}"]))

    if not spread_ok:
        out.append(("spread_widening", 0.85, ["execution_guard=spread_spike"]))
        out.append(("informed_trading_presence", 0.72, ["spread_guard_fail"]))
    if not slip_ok:
        out.append(("signed_order_flow_pressure", 0.8, ["execution_guard=slippage_spike"]))
    if not fill_ok:
        out.append(("volume_thinning", 0.78, ["execution_guard=fill_degradation"]))
    if not lat_ok or execution_health < 0.7:
        out.append(("latency_instability", max(0.5, 1.0 - execution_health), [
            f"execution_health={execution_health:.2f}",
        ]))
    if (not slip_ok or not spread_ok) and edge_strength > 0.35:
        out.append(("urgency_dilemma", 0.75, ["edge_active_under_exec_stress"]))
    if not slip_ok and not fill_ok:
        out.append(("size_pressure", 0.82, ["dual_liquidity_guard_fail"]))
    if replay_mismatch:
        out.append(("narrative_drift", 0.68, ["replay_signature_mismatch"]))

    if micro:
        if micro.amihud_proxy > 1e-6 and micro.fill_vol_ratio < 0.5:
            amihud_act = min(1.0, micro.amihud_proxy * 1e6 * 0.15 + (0.5 - micro.fill_vol_ratio))
            out.append(("signed_order_flow_pressure", amihud_act, [
                f"amihud_proxy={micro.amihud_proxy:.2e}",
                f"fill_vol_ratio={micro.fill_vol_ratio:.2f}",
            ]))
        if micro.continuation_resiliency < 0.35:
            out.append(("continuation_degrading", 0.65, [
                f"resiliency={micro.continuation_resiliency:.2f}",
            ]))
        if micro.vol_liquidity_elasticity > 0.45:
            out.append(("liquidity_thinning", min(1.0, micro.vol_liquidity_elasticity), [
                f"vol_liq_elasticity={micro.vol_liquidity_elasticity:.2f}",
            ]))
        if abs(micro.signed_pressure) > 0.55:
            out.append(("size_pressure", abs(micro.signed_pressure) * 0.85, [
                f"signed_pressure={micro.signed_pressure:.2f}",
            ]))

    if crowd_pressure >= 0.55:
        out.append(("panic_acceleration", crowd_pressure * 0.9, [f"crowd_pressure={crowd_pressure:.2f}"]))

    return out


def propagate_semantics(
    behaviors: list[tuple[str, float, list[str]]],
    regime: str,
    memory: SemanticMemoryStore | None = None,
) -> list[tuple[str, str, float, list[str]]]:
    """Expand active behaviors through relation graph → (behavior, meaning, confidence, evidence)."""
    regime_u = (regime or "UNKNOWN").upper()
    seen: set[str] = set()
    results: list[tuple[str, str, float, list[str]]] = []
    relations = merged_relations(memory)

    for behavior, activation, evidence in behaviors:
        if behavior not in seen:
            meaning = SEMANTIC_TRANSLATIONS.get(behavior, behavior.replace("_", " "))
            results.append((behavior, meaning, activation, evidence))
            seen.add(behavior)

        for rel in relations:
            if rel["from"] != behavior:
                continue
            regimes = rel.get("regimes") or ["*"]
            if "*" not in regimes and regime_u not in regimes:
                continue
            target = rel["to"]
            if target in seen:
                continue
            uncertainty = float(rel.get("uncertainty", 0.35))
            conf = min(1.0, activation * float(rel["weight"]) * (1.0 - uncertainty * 0.25))
            meaning = SEMANTIC_TRANSLATIONS.get(target, target.replace("_", " "))
            ev = evidence + [f"relation:{behavior}->{target}"]
            if rel.get("source"):
                ev.append(f"source:{rel['source']}")
            results.append((target, meaning, conf, ev))
            seen.add(target)

    return sorted(results, key=lambda x: x[2], reverse=True)
