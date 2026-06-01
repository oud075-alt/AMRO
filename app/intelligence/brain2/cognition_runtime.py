"""
Brain-2 — runtime semantic cognition orchestrator.

Role: behavioral semantics, contradiction awareness, contextual interpretation.
NOT execution authority — Brain-3 governance remains sole authority.
"""
from __future__ import annotations

import pandas as pd
from loguru import logger

from app.intelligence.brain2.audit_engine import run_sufficiency_audit
from app.intelligence.brain2.behavior_graph import active_behaviors, propagate_semantics
from app.intelligence.brain2.causal_confidence import (
    apply_causal_layer,
    aggregate_full_semantic_confidence,
    aggregate_governance_confidence,
)
from app.intelligence.brain2.cognitive_health import evaluate_cognitive_health
from app.intelligence.brain2.confidence_decay import apply_confidence_decay
from app.intelligence.brain2.contradiction_accumulator import update_contradiction_accumulation
from app.intelligence.brain2.contradiction_engine import contradiction_pressure, detect_contradictions
from app.intelligence.brain2.crowd_pressure import compute_crowd_pressure
from app.intelligence.brain2.memory_loader import load_semantic_memory
from app.intelligence.brain2.microstructure_grounding import (
    MicrostructureGrounding,
    compute_microstructure,
    impact_telemetry_penalty,
)
from app.intelligence.brain2.models import (
    Brain2CognitionState,
    CognitionRiskSurface,
    ExecutionSignals,
    GovernanceContextOutput,
    SemanticInterpretation,
    _level_from_float,
)
from app.intelligence.brain2.negative_memory import adjust_confidence_for_survival, apply_negative_memory_priority
from app.intelligence.brain2.persistent_store import load_persistent_state, save_persistent_state
from app.intelligence.brain2.replay_divergence import compute_replay_divergence
from app.intelligence.brain2.semantic_compression import compress_persistent_state
from app.intelligence.brain2.semantic_mutation import track_semantic_mutations
from app.intelligence.brain2.sequence_memory import update_sequence_memory
from app.intelligence.brain2.memory_first_cognition import (
    apply_abstention_to_confidence,
    build_memory_validated_interpretations,
    compute_memory_first_policy_report,
    filter_behaviors_for_propagation,
    retrieve_memory_context,
)
from app.intelligence.brain2.market_emotion_assessment import assess_market_emotion
from app.replay.replay_engine import load_replay_history
from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.ecology.ecosystem_runtime import EcosystemState
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState


def _load_thinking_framework(memory) -> dict:
    """Return the active Brain-2 thinking framework from semantic memory."""
    for entry in memory.entries:
        payload = entry.payload
        if payload.get("framework_id") == "B2_THINKING_FRAMEWORK_001":
            return {
                "framework_id": payload.get("framework_id"),
                "market_model": payload.get("market_model"),
                "core_principle": payload.get("core_principle"),
                "identity": payload.get("identity"),
                "required_output_fields": payload.get("required_output_fields"),
                "forbidden_behaviors": payload.get("forbidden_behaviors"),
                "critical_failure_modes": payload.get("critical_failure_modes"),
                "final_objective": payload.get("final_objective"),
                "governance_note": payload.get("governance_note"),
                "source": entry.source,
            }
    return {
        "framework_id": "B2_THINKING_FRAMEWORK_FALLBACK",
        "market_model": "behavioral_probabilistic_runtime_environment",
        "core_principle": "observable_behavior_is_not_absolute_truth",
        "required_output_fields": ["confidence", "uncertainty", "instability", "contradiction", "risk_level"],
        "forbidden_behaviors": ["certainty_language", "guaranteed_prediction", "absolute_conclusion"],
        "final_objective": ["survival", "execution_stability", "risk_reduction", "runtime_awareness"],
        "source": "runtime_fallback",
    }


def _estimate_probabilities(
    *,
    instability: float,
    entropy: float,
    structure_confidence: float,
    environment_quality: float,
    edge_strength: float,
    contra_pressure: float,
    accumulated_contra: float,
    exec_guards_ok: bool,
    micro: MicrostructureGrounding,
    crowd_pressure: float,
) -> tuple[float, float, float, float]:
    exec_penalty = 0.0 if exec_guards_ok else 0.18
    impact_pen = impact_telemetry_penalty(micro)
    micro_penalty = min(0.18, impact_pen + max(0, micro.instability_acceleration) * 0.08)
    inst_p = min(
        1.0,
        instability * 0.85 + entropy * 0.25 + contra_pressure * 0.3 + accumulated_contra * 0.25
        + exec_penalty + crowd_pressure * 0.12 + micro.instability_acceleration * 0.15 + impact_pen,
    )
    continuation_p = max(
        0.0,
        min(
            1.0,
            structure_confidence * environment_quality * micro.continuation_resiliency * (1.0 - contra_pressure * 0.45)
            - exec_penalty - micro_penalty,
        ),
    )
    fakeout_p = max(
        0.0,
        min(1.0, edge_strength * (1.0 - structure_confidence) * 0.9 + contra_pressure * 0.2 + crowd_pressure * 0.15),
    )
    exhaustion_p = max(0.0, min(1.0, (1.0 - structure_confidence) * 0.6 + instability * 0.25 + micro_penalty))
    return inst_p, continuation_p, fakeout_p, exhaustion_p


def _compress_for_governance(
    *,
    market_state: str,
    fakeout_p: float,
    instability_p: float,
    continuation_p: float,
    semantic_confidence: float,
    contra_pressure: float,
    accumulated_contra: float,
    top_meaning: str,
    exec_guards_ok: bool,
    cognitive_overload: bool,
) -> GovernanceContextOutput:
    effective_contra = max(contra_pressure, accumulated_contra)
    if not exec_guards_ok or effective_contra >= 0.55 or instability_p >= 0.65 or cognitive_overload:
        implication = "reduce exposure"
    elif fakeout_p >= 0.55:
        implication = "standby — elevated trap risk"
    elif continuation_p >= 0.55 and semantic_confidence >= 0.45:
        implication = "monitor — continuation context only"
    else:
        implication = "no participation upgrade"

    fakeout_risk = "elevated" if fakeout_p >= 0.5 else "moderate" if fakeout_p >= 0.3 else "low"
    if not exec_guards_ok:
        liquidity_state = "execution_stressed"
    elif market_state in ("unstable", "chaotic"):
        liquidity_state = "fragile"
    else:
        liquidity_state = "stable"
    continuation_state = "unstable" if continuation_p < 0.45 else "neutral" if continuation_p < 0.6 else "supportive"

    return GovernanceContextOutput(
        market_state=top_meaning or market_state,
        fakeout_risk=fakeout_risk,
        liquidity_state=liquidity_state,
        continuation_state=continuation_state,
        confidence_level=round(semantic_confidence, 4),
        governance_implication=implication,
    )


def _build_cognition_risk(
    *,
    contra_pressure: float,
    accumulated_contra: float,
    instability_p: float,
    exec_guards_ok: bool,
    micro: MicrostructureGrounding,
    replay_divergence_magnitude: float,
    replay_distrust: str,
    semantic_confidence: float,
    regime: str,
    distribution_shift: float,
    mutation_drift: float,
) -> CognitionRiskSurface:
    combined_contra = min(1.0, max(contra_pressure, accumulated_contra))
    exec_frag = 0.0 if exec_guards_ok else 0.72
    if micro.fill_vol_ratio < 0.35:
        exec_frag = max(exec_frag, 0.65)
    exec_frag = max(exec_frag, min(0.9, micro.impact_stress * 0.85 + impact_telemetry_penalty(micro)))

    regime_inst = min(1.0, distribution_shift * 0.55 + mutation_drift * 0.35 + (0.25 if regime in ("TRANSITIONAL", "VOLATILE") else 0.0))

    return CognitionRiskSurface(
        contradiction_pressure=combined_contra,
        instability_level=_level_from_float(instability_p, low="low", mid="moderate", high="elevated", crit="critical"),
        execution_fragility=_level_from_float(exec_frag, low="stable", mid="stressed", high="fragile", crit="critical"),
        replay_live_distrust=replay_distrust if replay_divergence_magnitude > 0 else "unknown",
        semantic_confidence=semantic_confidence,
        regime_instability=_level_from_float(regime_inst, low="stable", mid="shifting", high="unstable", crit="mutating"),
    )


def run_brain2_cognition(
    symbol: str,
    context: ContextState,
    market: MarketStructureState,
    edges: EdgeLayerResult | None,
    regime: str,
    *,
    replay_supported: bool = False,
    bar_count: int = 0,
    execution: ExecutionSignals | None = None,
    df: pd.DataFrame | None = None,
    micro: MicrostructureGrounding | None = None,
    ecology: EcosystemState | None = None,
    prior_snapshot: dict | None = None,
    replay_signature: str = "",
    persist_state: bool = True,
) -> Brain2CognitionState:
    memory = load_semantic_memory()
    thinking_framework = _load_thinking_framework(memory)
    persistent = load_persistent_state(symbol)
    bar_index = bar_count or int(persistent.get("bar_count", 0)) + 1

    exec_sig = execution or ExecutionSignals(replay_supported=replay_supported)
    if micro is None and df is not None and not df.empty:
        micro = compute_microstructure(df)
    if micro is None:
        micro = MicrostructureGrounding(0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 1.0)

    crowd = None
    if df is not None and ecology is not None and not df.empty:
        crowd = compute_crowd_pressure(
            df, ecology, micro,
            instability=market.instability_score,
            entropy=market.entropy_score,
        )
    crowd_val = crowd.crowd_pressure if crowd else 0.0

    prior = prior_snapshot or persistent.get("last_snapshot") or {}
    replay_history = load_replay_history(symbol, limit=10)

    data_gaps: list[str] = []
    if not memory.available:
        data_gaps.append("semantic_memory_packs_unavailable")

    edge_strength = edges.aggregate_strength if edges else 0.0
    env_q = edges.environment_quality if edges else 0.0
    edge_detected = bool(edges and edges.dominant_edge)

    behaviors = active_behaviors(
        instability=market.instability_score,
        entropy=market.entropy_score,
        distribution_shift=market.distribution_shift,
        synthetic_similarity=market.synthetic_similarity,
        structure_confidence=market.structure_confidence,
        environment_quality=env_q,
        edge_strength=edge_strength,
        market_state=market.market_state,
        slip_ok=exec_sig.slip_ok,
        spread_ok=exec_sig.spread_ok,
        fill_ok=exec_sig.fill_ok,
        lat_ok=exec_sig.lat_ok,
        execution_health=exec_sig.execution_health,
        replay_mismatch=exec_sig.replay_mismatch,
        micro=micro,
        crowd_pressure=crowd_val,
    )

    prior_sem = float(prior.get("semantic_confidence", 0.4))
    prior_cont = float(prior.get("continuation_probability", 0.45))

    replay_div = compute_replay_divergence(
        prior,
        micro=micro,
        structure_confidence=market.structure_confidence,
        semantic_confidence=prior_sem,
        continuation_probability=prior_cont,
        execution_health=exec_sig.execution_health,
        replay_signature=replay_signature,
        replay_history=replay_history,
    )
    impact_pen = impact_telemetry_penalty(micro)
    prior_accum = float(persistent.get("accumulated_contradiction_pressure", 0))

    drawdown = 0.0
    if df is not None and not df.empty and len(df) >= 20:
        c = df["close"].astype(float)
        peak = c.cummax()
        dd = (peak - c) / peak
        drawdown = float(dd.tail(20).max())

    # ── MANDATORY: memory retrieval BEFORE interpretation ──
    mem_ctx = retrieve_memory_context(
        behaviors,
        memory=memory,
        persistent=persistent,
        replay_div=replay_div,
        regime=regime,
        exec_guards_ok=exec_sig.exec_guards_ok,
        accumulated_contra=prior_accum,
        structure_confidence=market.structure_confidence,
        synthetic_similarity=market.synthetic_similarity,
        distribution_shift=market.distribution_shift,
        instability=market.instability_score,
        drawdown=drawdown,
    )
    if mem_ctx.global_support < 0.3:
        data_gaps.append("memory_support_low")
    if not memory.available:
        data_gaps.append("interpretation_blocked_without_pack_memory")

    behaviors_filtered = filter_behaviors_for_propagation(behaviors, mem_ctx)
    propagated = propagate_semantics(behaviors_filtered, regime, memory)

    contradictions = detect_contradictions(
        market_state=market.market_state,
        tradable=market.tradable,
        structure_confidence=market.structure_confidence,
        instability=market.instability_score,
        environment_quality=env_q,
        edge_strength=edge_strength,
        edge_detected=edge_detected,
        event_risk=context.event_risk,
        invalidate_trade=context.invalidate_trade,
        memory=memory,
        entropy=market.entropy_score,
        synthetic_similarity=market.synthetic_similarity,
        distribution_shift=market.distribution_shift,
        slip_ok=exec_sig.slip_ok,
        spread_ok=exec_sig.spread_ok,
        fill_ok=exec_sig.fill_ok,
        lat_ok=exec_sig.lat_ok,
        exec_guards_ok=exec_sig.exec_guards_ok,
        replay_mismatch=exec_sig.replay_mismatch or replay_div.signature_mismatch,
        contradiction_pressure_prior=prior_accum,
    )
    contra_p = contradiction_pressure(contradictions)

    contra_accum = update_contradiction_accumulation(
        persistent,
        bar_index=bar_index,
        regime=regime,
        records=contradictions,
    )
    if impact_pen >= 0.15:
        boosted = min(1.0, contra_accum.accumulated_pressure + impact_pen * 0.25)
        persistent["accumulated_contradiction_pressure"] = round(boosted, 4)
        contra_accum.accumulated_pressure = boosted

    mutation = track_semantic_mutations(
        persistent,
        bar_index=bar_index,
        regime=regime,
        active_behaviors=behaviors,
        structure_confidence=market.structure_confidence,
        edge_strength=edge_strength,
        contradiction_recurrence=contra_accum.recurrence_rate,
        continuation_probability=prior_cont,
    )

    raw_interps, blocked_unsupported, failure_overrides = build_memory_validated_interpretations(
        propagated,
        mem_ctx=mem_ctx,
        memory=memory,
        persistent=persistent,
        regime=regime,
        exec_guards_ok=exec_sig.exec_guards_ok,
        replay_div=replay_div,
        accumulated_contra=contra_accum.accumulated_pressure,
        structure_confidence=market.structure_confidence,
        instability=market.instability_score,
    )

    inst_p, cont_p, fake_p, exh_p = _estimate_probabilities(
        instability=market.instability_score,
        entropy=market.entropy_score,
        structure_confidence=market.structure_confidence,
        environment_quality=env_q,
        edge_strength=edge_strength,
        contra_pressure=contra_p,
        accumulated_contra=contra_accum.accumulated_pressure,
        exec_guards_ok=exec_sig.exec_guards_ok,
        micro=micro,
        crowd_pressure=crowd_val,
    )

    replay_ok = exec_sig.replay_supported and replay_div.cumulative_divergence < 0.22

    cognitive_health = evaluate_cognitive_health(
        interpretations=raw_interps,
        contradiction_pressure=contra_p,
        accumulated_contradiction_pressure=contra_accum.accumulated_pressure,
        synthetic_similarity=market.synthetic_similarity,
        semantic_confidence=prior_sem,
    )

    interpretations = apply_confidence_decay(
        raw_interps,
        bar_age=max(0, bar_count - 50),
        contradiction_count=len(contradictions),
        replay_supported=replay_ok,
        replay_divergence_magnitude=replay_div.cumulative_divergence,
        accumulated_contradiction_pressure=contra_accum.accumulated_pressure,
        cognitive_overload=cognitive_health.overload,
    )
    interpretations = apply_causal_layer(interpretations)

    semantic_conf = aggregate_full_semantic_confidence(interpretations)
    governance_conf = aggregate_governance_confidence(interpretations)

    neg = apply_negative_memory_priority(
        memory,
        persistent,
        edge_strength=edge_strength,
        structure_confidence=market.structure_confidence,
        semantic_confidence=semantic_conf,
        exec_guards_ok=exec_sig.exec_guards_ok,
        replay_divergence_magnitude=replay_div.divergence_magnitude,
        active_behaviors=[b for b, _, _ in behaviors],
    )
    semantic_conf = adjust_confidence_for_survival(semantic_conf, neg)
    governance_conf = adjust_confidence_for_survival(governance_conf, neg)

    if not exec_sig.exec_guards_ok:
        semantic_conf = max(0.05, semantic_conf * 0.72)
        governance_conf = max(0.05, governance_conf * 0.68)
    if replay_div.cumulative_divergence >= 0.35:
        damp = 1.0 - replay_div.cumulative_divergence * 0.5
        semantic_conf = max(0.05, semantic_conf * damp)
        governance_conf = max(0.05, governance_conf * damp)
    if impact_pen >= 0.2:
        semantic_conf = max(0.05, semantic_conf * (1.0 - impact_pen * 0.4))
        governance_conf = max(0.05, governance_conf * (1.0 - impact_pen * 0.35))

    mf_report = compute_memory_first_policy_report(
        interpretations,
        mem_ctx,
        blocked=blocked_unsupported,
        failure_overrides=failure_overrides,
        cognitive_overload=cognitive_health.overload,
    )
    governance_conf, semantic_conf = apply_abstention_to_confidence(
        governance_conf, semantic_conf, mf_report,
    )
    abstention_tendency = mf_report.abstention_tendency

    sequence = update_sequence_memory(
        symbol,
        bar_index=bar_index,
        regime=regime,
        instability=market.instability_score,
        entropy=market.entropy_score,
        structure_confidence=market.structure_confidence,
        edge_strength=edge_strength,
        market_state=market.market_state,
        persistent=persistent,
    )

    top_meaning = interpretations[0].meaning if interpretations else market.market_state
    gov_ctx = _compress_for_governance(
        market_state=market.market_state,
        fakeout_p=fake_p,
        instability_p=inst_p,
        continuation_p=cont_p,
        semantic_confidence=governance_conf,
        contra_pressure=contra_p,
        accumulated_contra=contra_accum.accumulated_pressure,
        top_meaning=top_meaning,
        exec_guards_ok=exec_sig.exec_guards_ok,
        cognitive_overload=cognitive_health.overload,
    )

    cognition_risk = _build_cognition_risk(
        contra_pressure=contra_p,
        accumulated_contra=contra_accum.accumulated_pressure,
        instability_p=inst_p,
        exec_guards_ok=exec_sig.exec_guards_ok,
        micro=micro,
        replay_divergence_magnitude=replay_div.cumulative_divergence,
        replay_distrust=replay_div.distrust_level,
        semantic_confidence=governance_conf,
        regime=regime,
        distribution_shift=market.distribution_shift,
        mutation_drift=mutation.drift_score,
    )

    exec_frag = 0.72 if not exec_sig.exec_guards_ok else min(0.9, micro.impact_stress * 0.85)
    panic_accel = crowd.panic_participation_acceleration if crowd else 0.0
    market_emotion = assess_market_emotion(
        market,
        micro=micro,
        continuation_p=cont_p,
        exhaustion_p=exh_p,
        instability_p=inst_p,
        fakeout_p=fake_p,
        crowd_pressure=crowd_val,
        panic_acceleration=panic_accel,
        edge_strength=edge_strength,
        drawdown=drawdown,
        exec_fragility=exec_frag,
        mutation_drift=mutation.drift_score,
        governance_confidence=governance_conf,
        abstention_tendency=abstention_tendency,
    )

    relation_count = len(memory.relations) + 18
    audit = run_sufficiency_audit(
        memory,
        runtime_flags={
            "spread": True,
            "slippage": True,
            "fill": True,
            "fill_degradation": not exec_sig.fill_ok,
            "latency": not exec_sig.lat_ok,
            "execution_guard": not exec_sig.exec_guards_ok,
            "execution_guard_wired": True,
            "replay_mismatch": replay_div.signature_mismatch,
            "replay_mismatch_wired": True,
            "replay_validation_wired": replay_div.divergence_magnitude > 0 or exec_sig.replay_supported,
            "contradiction_pressure": contra_accum.accumulated_pressure >= 0.35,
            "sequence_memory": len(sequence) > 0,
            "distribution_shift": market.distribution_shift >= 0.45,
            "synthetic_similarity": market.synthetic_similarity >= 0.55,
            "synthetic_similarity_high": market.synthetic_similarity >= 0.65,
            "instability": market.instability_score >= 0.55,
            "entropy": market.entropy_score >= 0.55,
            "semantic_confidence": semantic_conf < 0.5,
            "uncertainty": True,
            "confidence_decay": True,
            "governance_context": gov_ctx is not None,
            "regime": bool(regime),
            "ecology": ecology is not None,
            "crowd": crowd_val > 0.3,
            "failure": len(memory.failure_memories) > 0,
            "abstention": False,
            "runtime_health": False,
        },
        relation_count=relation_count,
        contradiction_template_count=len(memory.contradictions),
        sequence_count=len(memory.sequences),
    )

    for gap in audit.domain_gaps:
        if gap.status == "weak":
            data_gaps.append(f"weak_domain:{gap.domain}")

    memory_hits = list(dict.fromkeys(
        mem_ctx.pack_entry_ids[:3] + mem_ctx.relation_ids[:3] + mem_ctx.failure_ids[:2]
    ))[:8]

    uncertainty = "probabilistic behavioral interpretation only — not ground truth — memory-first policy active"
    if max(contra_p, contra_accum.accumulated_pressure) >= 0.5:
        uncertainty += " — contradictions elevated (accumulated)"
    if semantic_conf < 0.35:
        uncertainty += " — low semantic confidence"
    if not exec_sig.exec_guards_ok:
        uncertainty += " — execution pathology active"
    if replay_div.cumulative_divergence >= 0.28:
        uncertainty += f" — replay/live distrust={replay_div.distrust_level}"
    if cognitive_health.overload:
        uncertainty += " — cognitive overload"
    if mf_report.abstention_tendency >= 0.35:
        uncertainty += f" — memory-first abstention={mf_report.abstention_tendency:.2f}"
    if mf_report.memory_trusted_over_runtime:
        uncertainty += " — accumulated memory overrides runtime lean"

    persistent["last_snapshot"] = {
        "replay_signature": replay_signature,
        "fill_vol_ratio": micro.fill_vol_ratio,
        "spread_proxy": micro.spread_proxy,
        "execution_health": exec_sig.execution_health,
        "structure_confidence": market.structure_confidence,
        "semantic_confidence": semantic_conf,
        "governance_confidence": governance_conf,
        "continuation_probability": cont_p,
        "accumulated_contradiction_pressure": contra_accum.accumulated_pressure,
        "divergence_magnitude": replay_div.divergence_magnitude,
        "cumulative_divergence": replay_div.cumulative_divergence,
        "impact_stress": micro.impact_stress,
        "mutation_drift": mutation.drift_score,
    }
    persistent["bar_count"] = bar_index
    compress_persistent_state(persistent, bar_index=bar_index)
    if persist_state:
        save_persistent_state(symbol, persistent)

    state = Brain2CognitionState(
        symbol=symbol,
        regime=regime,
        interpretations=interpretations,
        contradictions=contradictions,
        sequence=sequence,
        governance_context=gov_ctx,
        instability_probability=inst_p,
        continuation_probability=cont_p,
        fakeout_probability=fake_p,
        exhaustion_probability=exh_p,
        semantic_confidence=semantic_conf,
        governance_confidence=governance_conf,
        contradiction_pressure=contra_p,
        accumulated_contradiction_pressure=contra_accum.accumulated_pressure,
        memory_hits=memory_hits,
        data_gaps=data_gaps,
        uncertainty_note=uncertainty,
        audit_report=audit.to_dict(),
        execution_signals=exec_sig.to_dict(),
        cognition_risk=cognition_risk.to_dict(),
        replay_divergence=replay_div.to_dict(),
        cognitive_health=cognitive_health.to_dict(),
        microstructure=micro.to_dict(),
        crowd_pressure=crowd.to_dict() if crowd else None,
        impact_telemetry=micro.rolling_telemetry,
        memory_first_policy={
            **mf_report.to_dict(),
            "retrieval": mem_ctx.to_dict(),
        },
        abstention_tendency=abstention_tendency,
        market_emotion=market_emotion.to_dict(),
        thinking_framework=thinking_framework,
    )

    logger.info(
        f"[Brain2] {symbol} gov_conf={governance_conf:.2f} sem_conf={semantic_conf:.2f} "
        f"mem_support={mem_ctx.global_support:.2f} abstain={abstention_tendency:.2f} "
        f"blocked={blocked_unsupported} health={cognitive_health.health_level}"
    )
    return state
