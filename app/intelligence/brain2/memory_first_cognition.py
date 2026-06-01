"""
Memory-first cognition policy — mandatory runtime interpretation gate.

Brain-2 MUST NOT: runtime → interpretation direct.
Required path: runtime → memory retrieval → validation → probabilistic interpretation only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field
from typing import Any

from app.intelligence.brain2.causal_confidence import CAUSAL_OBSERVED, CAUSAL_SPECULATIVE, classify_causal_level
from app.intelligence.brain2.memory_loader import SemanticMemoryStore
from app.intelligence.brain2.models import SemanticInterpretation
from app.intelligence.brain2.replay_divergence import ReplayDivergenceMetrics


# Behaviors that imply optimistic continuation — penalized when accumulated memory conflicts
_CONTINUATION_LEAN: set[str] = {
    "breakout_without_continuation",
    "continuation_degrading",
    "volatility_expansion",
    "panic_acceleration",
    "size_pressure",
}

# Failure patterns that override optimistic interpretations
_FAILURE_CONFLICT_TRIGGERS: dict[str, list[str]] = {
    "breakout_without_continuation": ["edge_without_structure", "crowd_chase", "false_confidence"],
    "weak_edge_environment": ["edge_without_structure"],
    "noise_trader_sentiment_shift": ["high_entropy", "crowd_chase"],
    "narrative_drift": ["replay_signature_mismatch", "replay_live"],
    "synthetic_similarity": ["high_entropy", "synthetic"],
}


@dataclass
class MemoryRetrievalContext:
    """Result of mandatory memory retrieval before any interpretation."""
    pack_entry_ids: list[str]
    relation_ids: list[str]
    failure_ids: list[str]
    contra_clusters: list[str]
    mutation_behaviors: list[str]
    sequence_behaviors: list[str]
    replay_trust: float
    regime_prior: str
    accumulated_contra: float
    behavior_support: dict[str, float]
    global_support: float
    pack_gate_sources: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["global_support"] = round(float(d["global_support"]), 4)
        d["replay_trust"] = round(float(d["replay_trust"]), 4)
        d["accumulated_contra"] = round(float(d["accumulated_contra"]), 4)
        return d


@dataclass
class MemoryFirstPolicyReport:
    policy: str
    abstention_tendency: float
    avg_memory_support: float
    blocked_unsupported: int
    failure_overrides: int
    memory_trusted_over_runtime: bool

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k in ("abstention_tendency", "avg_memory_support"):
            d[k] = round(float(d[k]), 4)
        return d


def _behavior_in_payload(behavior: str, payload: dict[str, Any]) -> bool:
    blob = str(payload).lower()
    b = behavior.lower().replace("_", " ")
    parts = behavior.lower().split("_")
    return behavior.lower() in blob or b in blob or any(p in blob for p in parts if len(p) > 3)


def _score_behavior_support(
    behavior: str,
    memory: SemanticMemoryStore,
    persistent: dict[str, Any],
    regime: str,
) -> tuple[float, list[str]]:
    sources: list[str] = []
    score = 0.0

    for rel in memory.relations:
        src = str(rel.get("from_behavior") or rel.get("from") or "")
        tgt = str(rel.get("to_behavior") or rel.get("to") or "")
        if behavior in (src, tgt) or _behavior_in_payload(behavior, rel):
            score = max(score, 0.55)
            rid = str(rel.get("relation_id", ""))
            if rid:
                sources.append(rid)

    for entry in memory.entries:
        if _behavior_in_payload(behavior, entry.payload):
            score = max(score, 0.45 + entry.confidence * 0.2)
            sources.append(entry.entry_id)

    for fm in memory.failure_memories:
        if _behavior_in_payload(behavior, fm):
            score = max(score, 0.5)
            sources.append(str(fm.get("failure_id", "failure")))

    contra_log = persistent.get("contradiction_log") or []
    for c in contra_log[-30:]:
        cluster = str(c.get("cluster", "")).lower()
        if behavior.split("_")[0] in cluster or behavior.replace("_", " ") in cluster:
            score = max(score, 0.4)
            sources.append(f"contra:{cluster}")

    for m in (persistent.get("semantic_mutations") or [])[-20:]:
        if str(m.get("behavior", "")) == behavior:
            score = max(score, 0.42)
            sources.append(f"mutation:{behavior}")

    for s in (persistent.get("sequence_log") or [])[-10:]:
        if behavior in str(s.get("behavior", "")):
            score = max(score, 0.38)
            sources.append(f"sequence:{s.get('key', '')}")

    regimes = memory.relations  # regime boost if relation lists regime
    regime_u = regime.upper()
    for rel in regimes:
        if behavior in (str(rel.get("from", "")), str(rel.get("to", ""))):
            rlist = rel.get("regimes") or ["*"]
            if "*" in rlist or regime_u in rlist:
                score = min(1.0, score + 0.08)

    return min(1.0, score), sources[:6]


def _runtime_match_hit(
    match: dict[str, Any],
    *,
    structure_confidence: float,
    synthetic_similarity: float,
    distribution_shift: float,
    instability: float,
    drawdown: float,
) -> bool:
    if not match:
        return False
    synth_min = float(match.get("synthetic_similarity_min") or 0)
    struct_max = float(match.get("structure_confidence_max", 1))
    shift_min = float(match.get("distribution_shift_min") or 0)
    inst_min = float(match.get("instability_min") or 0)
    dd_min = float(match.get("drawdown_min") or 0)
    if synth_min and synthetic_similarity < synth_min:
        return False
    if struct_max < 1 and structure_confidence > struct_max:
        return False
    if shift_min and distribution_shift < shift_min:
        return False
    if inst_min and instability < inst_min:
        return False
    if dd_min and drawdown < dd_min:
        return False
    return True


def _apply_pack_uncertainty_gates(
    global_support: float,
    *,
    memory: SemanticMemoryStore,
    structure_confidence: float,
    synthetic_similarity: float,
    distribution_shift: float,
    instability: float,
    drawdown: float,
) -> tuple[float, list[str]]:
    """Apply ingested uncertainty / reality-verification pack rules."""
    support = global_support
    sources: list[str] = []

    for rel in memory.relations:
        match = rel.get("runtime_match") or {}
        if not rel.get("elevation_block") and not rel.get("memory_support_cap") and not match:
            continue
        if not _runtime_match_hit(
            match,
            structure_confidence=structure_confidence,
            synthetic_similarity=synthetic_similarity,
            distribution_shift=distribution_shift,
            instability=instability,
            drawdown=drawdown,
        ):
            continue
        cap = float(rel.get("memory_support_cap") or 0.34)
        support = min(support, cap)
        rid = str(rel.get("relation_id") or rel.get("verification_id") or "")
        if rid:
            sources.append(rid)

    for entry in memory.entries:
        row = entry.payload
        vid = row.get("verification_id")
        if not vid or not row.get("elevation_block_when_unmet"):
            continue
        match = row.get("runtime_match") or {}
        if not _runtime_match_hit(
            match,
            structure_confidence=structure_confidence,
            synthetic_similarity=synthetic_similarity,
            distribution_shift=distribution_shift,
            instability=instability,
            drawdown=drawdown,
        ):
            continue
        cap = float(row.get("memory_support_cap") or 0.32)
        support = min(support, cap)
        sources.append(str(vid))

    return support, sources


def retrieve_memory_context(
    behaviors: list[tuple[str, float, list[str]]],
    *,
    memory: SemanticMemoryStore,
    persistent: dict[str, Any],
    replay_div: ReplayDivergenceMetrics,
    regime: str,
    exec_guards_ok: bool,
    accumulated_contra: float,
    structure_confidence: float = 0.5,
    synthetic_similarity: float = 0.0,
    distribution_shift: float = 0.0,
    instability: float = 0.0,
    drawdown: float = 0.0,
) -> MemoryRetrievalContext:
    """Mandatory step — retrieve and score memory before interpretation."""
    behavior_support: dict[str, float] = {}
    all_sources: list[str] = []

    for behavior, activation, evidence in behaviors:
        base, sources = _score_behavior_support(behavior, memory, persistent, regime)
        causal = classify_causal_level(behavior, evidence)
        if causal == CAUSAL_OBSERVED and any("execution_guard" in e for e in evidence):
            base = max(base, 0.45)
            sources.append("runtime_observed")
        elif causal == CAUSAL_OBSERVED:
            base = max(base, 0.35)
        if not memory.available:
            base = min(base, 0.2)
        behavior_support[behavior] = round(base * max(0.5, activation), 4)
        all_sources.extend(sources)

    replay_trust = replay_div.replay_reliability
    if replay_div.cumulative_divergence >= 0.35:
        replay_trust = min(replay_trust, 0.35)

    global_support = sum(behavior_support.values()) / max(1, len(behavior_support)) if behavior_support else 0.0
    if accumulated_contra >= 0.45:
        global_support *= max(0.35, 1.0 - accumulated_contra * 0.55)
    if not exec_guards_ok:
        global_support *= 0.75

    global_support, pack_gate_sources = _apply_pack_uncertainty_gates(
        global_support,
        memory=memory,
        structure_confidence=structure_confidence,
        synthetic_similarity=synthetic_similarity,
        distribution_shift=distribution_shift,
        instability=instability,
        drawdown=drawdown,
    )

    pack_ids = [e.entry_id for e in memory.entries[:12]]
    rel_ids = [str(r.get("relation_id", "")) for r in memory.relations[:12] if r.get("relation_id")]
    fail_ids = [str(f.get("failure_id", "")) for f in memory.failure_memories]
    contra_clusters = list({str(c.get("cluster", "")) for c in (persistent.get("contradiction_log") or [])[-15:]})
    mutations = [str(m.get("behavior", "")) for m in (persistent.get("semantic_mutations") or [])[-8:]]
    sequences = [str(s.get("behavior", "")) for s in (persistent.get("sequence_log") or [])[-6:]]

    return MemoryRetrievalContext(
        pack_entry_ids=pack_ids,
        relation_ids=rel_ids,
        failure_ids=fail_ids,
        contra_clusters=contra_clusters,
        mutation_behaviors=mutations,
        sequence_behaviors=sequences,
        replay_trust=round(replay_trust, 4),
        regime_prior=str(persistent.get("last_regime", "")),
        accumulated_contra=accumulated_contra,
        behavior_support=behavior_support,
        global_support=round(global_support, 4),
        pack_gate_sources=pack_gate_sources,
    )


def filter_behaviors_for_propagation(
    behaviors: list[tuple[str, float, list[str]]],
    mem_ctx: MemoryRetrievalContext,
) -> list[tuple[str, float, list[str]]]:
    """Block free propagation — only memory-supported or observed runtime behaviors."""
    out: list[tuple[str, float, list[str]]] = []
    for behavior, activation, evidence in behaviors:
        support = mem_ctx.behavior_support.get(behavior, 0.0)
        causal = classify_causal_level(behavior, evidence)
        if causal == CAUSAL_OBSERVED:
            out.append((behavior, activation, evidence + ["memory_first:observed_allowed"]))
        elif support >= 0.22:
            out.append((behavior, activation, evidence + [f"memory_support={support:.2f}"]))
        elif support >= 0.12 and causal <= 2:
            out.append((behavior, activation * 0.65, evidence + [f"memory_support_weak={support:.2f}"]))
    return out


def _regime_alignment(behavior: str, regime: str, mem_ctx: MemoryRetrievalContext) -> str:
    if mem_ctx.regime_prior and mem_ctx.regime_prior != regime:
        if behavior in ("distribution_shift", "regime_mutation", "narrative_drift"):
            return "misaligned"
        return "neutral"
    if behavior in mem_ctx.mutation_behaviors:
        return "neutral"
    return "aligned"


def _execution_survivability(exec_guards_ok: bool, behavior: str) -> str:
    if not exec_guards_ok:
        return "rejected"
    if behavior in ("urgency_dilemma", "implementation_shortfall", "spread_widening", "volume_thinning"):
        return "stressed"
    return "supported"


def _failure_conflicts(behavior: str, memory: SemanticMemoryStore, persistent: dict[str, Any]) -> bool:
    triggers = _FAILURE_CONFLICT_TRIGGERS.get(behavior, [])
    if not triggers:
        return False
    for fm in memory.failure_memories:
        pats = [str(t).lower() for t in fm.get("trigger_pattern") or []]
        if any(t in " ".join(pats) for t in triggers):
            reinf = persistent.get("failure_reinforcement") or {}
            fid = str(fm.get("failure_id", ""))
            if reinf.get(fid, 0) > 0 or _behavior_in_payload(behavior, fm):
                return True
    return False


def build_memory_validated_interpretations(
    propagated: list[tuple[str, str, float, list[str]]],
    *,
    mem_ctx: MemoryRetrievalContext,
    memory: SemanticMemoryStore,
    persistent: dict[str, Any],
    regime: str,
    exec_guards_ok: bool,
    replay_div: ReplayDivergenceMetrics,
    accumulated_contra: float,
    structure_confidence: float = 0.5,
    instability: float = 0.0,
) -> tuple[list[SemanticInterpretation], int, int]:
    """Build interpretations only after memory validation — drop unsupported freeform semantics."""
    interps: list[SemanticInterpretation] = []
    blocked = 0
    failure_overrides = 0

    for behavior, meaning, conf, evidence in propagated[:10]:
        propagated_flag = any("relation:" in e for e in evidence)
        causal = classify_causal_level(behavior, evidence, propagated=propagated_flag)
        support = mem_ctx.behavior_support.get(behavior, 0.0)
        if propagated_flag:
            parent = behavior
            for e in evidence:
                if e.startswith("relation:"):
                    parent = e.split("->")[0].replace("relation:", "")
                    break
            support = max(support, mem_ctx.behavior_support.get(parent, 0.0) * 0.85)
            if not any("source:" in e for e in evidence):
                support = min(support, 0.28)

        memory_sources = mem_ctx.relation_ids[:2] + mem_ctx.pack_entry_ids[:2]
        _, srcs = _score_behavior_support(behavior, memory, persistent, regime)
        memory_sources = list(dict.fromkeys(srcs + memory_sources))[:5]

        if causal == CAUSAL_SPECULATIVE and support < 0.35:
            blocked += 1
            continue
        if support < 0.18 and causal >= 3:
            blocked += 1
            continue
        if support < 0.12 and not propagated_flag:
            blocked += 1
            continue

        conf = conf * max(0.25, support)
        conf *= mem_ctx.replay_trust

        contra_status = "clear"
        if accumulated_contra >= 0.4 and behavior in _CONTINUATION_LEAN:
            conf *= 0.45
            contra_status = "conflicts_accumulated_memory"
        if _failure_conflicts(behavior, memory, persistent):
            calm_stable = structure_confidence >= 0.65 and instability < 0.35
            if calm_stable:
                conf = min(conf, 0.28)
                if contra_status == "clear":
                    contra_status = "failure_monitor"
            else:
                conf = min(conf, 0.1)
                contra_status = "failure_override"
                failure_overrides += 1

        if replay_div.cumulative_divergence >= 0.3:
            conf *= max(0.3, 1.0 - replay_div.cumulative_divergence * 0.6)
            if contra_status == "clear":
                contra_status = "replay_distrust"

        regime_align = _regime_alignment(behavior, regime, mem_ctx)
        if regime_align == "misaligned":
            conf *= 0.55

        exec_surv = _execution_survivability(exec_guards_ok, behavior)
        if exec_surv == "rejected":
            conf *= 0.35

        if support < 0.3:
            uncertainty = "high"
        elif support < 0.5 or contra_status != "clear":
            uncertainty = "moderate"
        elif mem_ctx.replay_trust < 0.5:
            uncertainty = "moderate"
        else:
            uncertainty = "low"

        if support < 0.25:
            uncertainty = "extreme"

        prob_meaning = f"memory-similar pattern ({support:.0%} support) — {meaning}"
        if contra_status == "failure_override":
            prob_meaning = f"failure memory conflict — distrust ({meaning})"

        interps.append(SemanticInterpretation(
            behavior=behavior,
            meaning=prob_meaning,
            confidence=round(min(1.0, conf), 4),
            evidence=evidence + [f"memory_sources={','.join(memory_sources[:3])}"],
            regime=regime,
            memory_sources=memory_sources,
            memory_support=round(support, 4),
            contradiction_status=contra_status,
            replay_trust=round(mem_ctx.replay_trust, 4),
            execution_survivability=exec_surv,
            regime_alignment=regime_align,
            uncertainty_level=uncertainty,
        ))

    return interps, blocked, failure_overrides


def compute_memory_first_policy_report(
    interpretations: list[SemanticInterpretation],
    mem_ctx: MemoryRetrievalContext,
    *,
    blocked: int,
    failure_overrides: int,
    cognitive_overload: bool,
) -> MemoryFirstPolicyReport:
    supports = [getattr(i, "memory_support", 0.0) for i in interpretations]
    avg = sum(supports) / max(1, len(supports)) if supports else 0.0

    abstention = 0.0
    if mem_ctx.global_support < 0.25:
        abstention += 0.35
    elif mem_ctx.global_support < 0.4:
        abstention += 0.2
    if mem_ctx.pack_gate_sources:
        abstention += 0.12
    if mem_ctx.accumulated_contra >= 0.45:
        abstention += 0.25
    if mem_ctx.replay_trust < 0.45:
        abstention += 0.2
    if failure_overrides > 0:
        abstention += 0.15
    if blocked >= 3:
        abstention += 0.1
    if cognitive_overload:
        abstention += 0.15
    abstention = min(1.0, abstention)

    memory_trusted = (
        mem_ctx.accumulated_contra >= 0.35
        or mem_ctx.replay_trust < 0.5
        or failure_overrides > 0
    )

    return MemoryFirstPolicyReport(
        policy="memory_first_v1",
        abstention_tendency=abstention,
        avg_memory_support=avg,
        blocked_unsupported=blocked,
        failure_overrides=failure_overrides,
        memory_trusted_over_runtime=memory_trusted,
    )


def apply_abstention_to_confidence(
    governance_conf: float,
    semantic_conf: float,
    report: MemoryFirstPolicyReport,
) -> tuple[float, float]:
    """Low memory support → distrust, never narrative fill."""
    if report.abstention_tendency < 0.2:
        return governance_conf, semantic_conf
    damp = max(0.35, 1.0 - report.abstention_tendency * 0.55)
    return (
        max(0.05, governance_conf * damp),
        max(0.05, semantic_conf * damp),
    )
