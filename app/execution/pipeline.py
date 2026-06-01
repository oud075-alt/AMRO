"""
Mandatory execution flow (sole pipeline):
  AI#1 Context → AI#2 Market Runtime → Brain-2 Semantic Cognition → Edge → Abstention
  → AI#3 Governance (Brain-2 advisory) → Capital Allocation → Execution Runtime → Telemetry + Replay
"""
from __future__ import annotations

from typing import Any

import pandas as pd
from loguru import logger

from app.intelligence.context.context_state import ContextState, load_context_state
from app.intelligence.market_data import fetch_market_data
from app.intelligence.market_runtime.structure import compute_market_audit
from app.intelligence.market_runtime.edge_lab.edge_runtime import run_edge_layer
from app.intelligence.market_runtime.fingerprint import compute_fingerprint, evaluate_market_identity
from app.intelligence.market_runtime.ecology import evaluate_ecosystem, audit_ecology_balance
from app.intelligence.market_runtime.regime import evaluate_regime
from app.intelligence.market_runtime.abstention.adaptive_abstention import evaluate_abstention
from app.intelligence.market_runtime.abstention.abstention_pressure import compute_abstention_pressure
from app.intelligence.market_runtime.abstention.edge_believability import compute_runtime_believability
from app.intelligence.market_runtime.abstention.edge_survival_monitor import evaluate_edge_survival
from app.governance.runtime_constitution.governance_engine import evaluate_governance
from app.intelligence.brain2 import run_brain2_cognition
from app.intelligence.brain2.models import ExecutionSignals
from app.execution.capital_allocator import allocate_capital
from app.execution.slippage_guard import check_slippage
from app.execution.spread_guard import check_spread
from app.execution.fill_quality_monitor import check_fill_quality
from app.execution.latency_guard import check_latency
from app.runtime.runtime_health import evaluate_runtime_health, RuntimeStateLevel
from app.runtime.runtime_watchdog import check_pipeline_integrity, execution_permitted
from app.runtime.crash_recovery import recover_runtime
from app.replay.replay_engine import load_snapshot, store_snapshot
from app.replay.replay_validator import validate_replay
from app.telemetry.decision_lineage import build_lineage, record_lineage
from app.ui.market_environment import compute_market_environment_card


def _drawdown_proxy(df: pd.DataFrame) -> float:
    c = df["close"]
    peak = c.cummax()
    dd = (peak - c) / peak
    tail = dd.tail(20)
    if len(tail) < 2:
        return 0.0
    return max(0.0, float(tail.iloc[-1] - tail.min()))


def run_execution_pipeline(
    symbol: str,
    interval: str = "1h",
    days: int = 30,
    run_context_llm: bool = True,
    log_decision: bool = True,
    open_positions: int = 0,
    execution_health: float = 1.0,
    df: pd.DataFrame | None = None,
    persist: bool = True,
    state_symbol: str | None = None,
    publish_to_ea: bool = True,
) -> dict[str, Any] | None:
    store_key = state_symbol or symbol
    logger.info(f"[ExecutionPipeline] START {symbol}" + (f" store={store_key}" if store_key != symbol else ""))

    if df is None:
        df = fetch_market_data(symbol=symbol, interval=interval, days=days)
    if df.empty or len(df) < 50:
        return None

    price = float(df["close"].iloc[-1])
    bar_ts = str(df.index[-1])

    # AI #1 — Context Advisory
    context: ContextState = load_context_state(symbol, run_llm=run_context_llm)

    # AI #2 — Market Runtime Intelligence
    market = compute_market_audit(df)
    edges = run_edge_layer(df, symbol)
    fingerprint = compute_fingerprint(df)
    identity = evaluate_market_identity(df, edges)
    ecology_state = evaluate_ecosystem(df, market, edges)
    ecology_audit = audit_ecology_balance(ecology_state)
    regime = evaluate_regime(df)
    health = evaluate_edge_survival(edges, market.synthetic_similarity)
    believability = compute_runtime_believability(edges, fingerprint, health)

    # Behavioral Edge Detection (within edge_lab run above)

    prior = load_snapshot(store_key) or {} if persist else {}
    replay_sig = ""
    if edges.dominant_edge:
        dom = next((e for e in edges.edges if e.edge_id == edges.dominant_edge), None)
        replay_sig = dom.replay_signature if dom else ""

    replay_mismatch = bool(prior and replay_sig and prior.get("replay_signature") != replay_sig)

    slip_ok, slip_reason = check_slippage(df)
    spread_ok, spread_reason = check_spread(df)
    fill_ok, fill_reason = check_fill_quality(df)
    lat_ok, lat_reason = check_latency(execution_health)
    exec_guards_ok = slip_ok and spread_ok and fill_ok and lat_ok
    exec_signals = ExecutionSignals(
        slip_ok=slip_ok,
        spread_ok=spread_ok,
        fill_ok=fill_ok,
        lat_ok=lat_ok,
        exec_guards_ok=exec_guards_ok,
        execution_health=execution_health,
        slip_reason=slip_reason,
        spread_reason=spread_reason,
        fill_reason=fill_reason,
        lat_reason=lat_reason,
        replay_mismatch=replay_mismatch,
        replay_supported=bool(prior),
    )

    # Brain-2 — Semantic cognition (advisory; Brain-3 remains authority)
    brain2 = run_brain2_cognition(
        store_key,
        context,
        market,
        edges,
        regime.regime,
        replay_supported=bool(prior),
        bar_count=len(df),
        execution=exec_signals,
        df=df,
        ecology=ecology_state,
        prior_snapshot=prior,
        replay_signature=replay_sig,
        persist_state=persist,
    )

    runtime_health = evaluate_runtime_health(
        df, symbol, context_error=bool(context.error), replay_mismatch=replay_mismatch
    )
    runtime_health = recover_runtime(runtime_health)

    # Adaptive Abstention
    abstention = evaluate_abstention(
        df, context, market, edges, runtime_health.level, _drawdown_proxy(df)
    )
    abst_pressure = compute_abstention_pressure(market, abstention)

    # AI #3 — Governance (Brain-2 advisory input; sole execution authority)
    gov = evaluate_governance(context, market, edges=edges, ecology=ecology_audit, brain2=brain2)

    # Capital Allocation (reads gov + abstention outputs only)
    allocation = allocate_capital(
        gov,
        abstention,
        market,
        edges,
        fingerprint=fingerprint,
        health=health,
        believability=believability,
        rolling_dd=_drawdown_proxy(df),
        open_positions=open_positions,
        execution_health=execution_health,
        governance_pressure=gov.governance_pressure,
        abstention_pressure=abst_pressure,
        bar_count=len(df),
    )

    guard_reasons = []
    if not slip_ok:
        guard_reasons.append(slip_reason)
    if not spread_ok:
        guard_reasons.append(spread_reason)
    if not fill_ok:
        guard_reasons.append(fill_reason)
    if not lat_ok:
        guard_reasons.append(lat_reason)

    integrity = check_pipeline_integrity(True, True, True, True, True)
    exec_ok, fail_reason = execution_permitted(runtime_health)

    runtime_blocked = (
        not exec_ok
        or runtime_health.level in (RuntimeStateLevel.DISABLED, RuntimeStateLevel.UNTRUSTED)
        or not integrity.ok
    )

    final_approved = (
        gov.approved
        and not abstention.abstain
        and not runtime_blocked
        and exec_guards_ok
        and allocation.position_limit > 0
        and ecology_audit.passed
    )

    if not exec_ok:
        final_reason = f"runtime_fail_closed:{fail_reason}"
    elif runtime_blocked:
        final_reason = f"runtime_fail_closed:{runtime_health.level.value}"
    elif abstention.abstain:
        final_reason = f"abstention_override:{abstention.abstention_reason}"
    elif not exec_guards_ok:
        final_reason = f"execution_guard_fail:{';'.join(guard_reasons)}"
    elif not ecology_audit.passed:
        final_reason = f"ecology_block:{';'.join(ecology_audit.blockers)}"
    elif not gov.approved:
        final_reason = f"governance_{gov.verdict.value}:{gov.reason}"
    elif allocation.position_limit <= 0:
        final_reason = f"allocation_zero:{allocation.allocation_reason}"
    else:
        final_reason = "execution_permitted_within_limits"

    position_limit = allocation.position_limit if final_approved else 0.0

    ea_permission = "ABSTAIN"
    if final_approved:
        ea_permission = gov.verdict.value
    elif runtime_blocked or not exec_guards_ok or not ecology_audit.passed or not gov.approved:
        ea_permission = "BLOCK"

    if persist and publish_to_ea:
        try:
            from app.api.ea_bridge import publish_decision

            publish_decision(
                symbol=symbol,
                approved=final_approved,
                permission=ea_permission,
                max_lot_scale=position_limit,
                risk_state="NORMAL" if final_approved else "NO_TRADE",
                governance_verdict=gov.verdict.value,
                execution_reason=final_reason,
                uncertainty=brain2.abstention_tendency,
                confidence=brain2.governance_confidence,
            )
        except Exception as exc:
            logger.warning(f"[ExecutionPipeline] EA permission publish failed: {exc}")

    current_snap = {
        "bar_index": len(df),
        "replay_signature": replay_sig,
        "governance_verdict": gov.verdict.value,
        "runtime_trust": abstention.runtime_trust_score,
        "abstention_pressure": abst_pressure,
        "fill_vol_ratio": brain2.microstructure.get("fill_vol_ratio") if brain2.microstructure else None,
        "spread_proxy": brain2.microstructure.get("spread_proxy") if brain2.microstructure else None,
        "execution_health": execution_health,
        "execution_guards_ok": exec_guards_ok,
        "structure_confidence": market.structure_confidence,
        "semantic_confidence": brain2.semantic_confidence,
        "governance_confidence": brain2.governance_confidence,
        "continuation_probability": brain2.continuation_probability,
        "divergence_magnitude": (brain2.replay_divergence or {}).get("divergence_magnitude"),
        "cumulative_divergence": (brain2.replay_divergence or {}).get("cumulative_divergence"),
        "accumulated_contradiction_pressure": brain2.accumulated_contradiction_pressure,
        "impact_stress": (brain2.microstructure or {}).get("impact_stress"),
        "mutation_drift": (brain2.cognitive_health or {}).get("narrative_recursion_pressure"),
        "contradiction_pressure": brain2.contradiction_pressure,
        "regime": regime.regime,
    }
    replay_validation = validate_replay(prior, current_snap) if prior else None
    if persist:
        store_snapshot(store_key, current_snap)

    runtime_metrics = {
        "runtime_trust": abstention.runtime_trust_score,
        "market_quality": allocation.market_quality_score,
        "abstention_pressure": abst_pressure,
        "governance_state": gov.verdict.value,
        "governance_pressure": gov.governance_pressure,
        "risk_pressure": allocation.risk_pressure,
        "exposure_state": allocation.exposure_state,
        "runtime_health": runtime_health.level.value,
        "edge_environment_quality": edges.environment_quality,
        "market_state": market.market_state,
        "execution_health": execution_health,
        "execution_guards_ok": exec_guards_ok,
    }

    market_environment = compute_market_environment_card(
        df, market, gov, abstention, edges, context, regime.regime
    ).to_dict()

    if log_decision and persist:
        record_lineage(
            build_lineage(
                symbol=symbol,
                context_state=context.to_dict(),
                market_runtime_state={**market.to_dict(), "identity": identity.to_dict()},
                edge_state=edges.to_dict(),
                abstention_state={**abstention.to_dict(), "abstention_pressure": abst_pressure},
                governance_state=gov.to_dict(),
                runtime_state=runtime_health.to_dict(),
                allocation_state=allocation.to_dict(),
                execution_outcome={
                    "approved": final_approved,
                    "position_limit": position_limit,
                    "integrity_ok": integrity.ok,
                    "replay_validation": replay_validation.to_dict() if replay_validation else None,
                    "brain2_cognition": brain2.to_dict(),
                },
                final_execution_reason=final_reason,
                approved=final_approved,
                position_limit=position_limit,
            )
        )

    logger.info(f"[ExecutionPipeline] DONE {symbol} approved={final_approved} verdict={gov.verdict.value}")

    return {
        "symbol": symbol,
        "timestamp": bar_ts,
        "price": price,
        "context": context,
        "market_audit": market,
        "edges": edges,
        "abstention": abstention,
        "governance": gov,
        "allocation": allocation,
        "runtime_health": runtime_health,
        "regime": regime,
        "approved": final_approved,
        "direction": "ABSTAIN",
        "position_limit": position_limit,
        "final_execution_reason": final_reason,
        "runtime_metrics": runtime_metrics,
        "market_environment": market_environment,
        "replay_validation": replay_validation.to_dict() if replay_validation else None,
        "brain2_cognition": brain2.to_dict(),
        "architecture": "amro_consolidated_runtime_v8_brain2",
    }
