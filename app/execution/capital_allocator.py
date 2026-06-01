"""
Sole capital allocator — position sizing from governance + abstention inputs.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

from loguru import logger

from app.governance.runtime_constitution.governance_engine import GovernanceDecision
from app.intelligence.market_runtime.abstention.adaptive_abstention import AbstentionDecision
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.abstention.edge_believability import compute_runtime_believability
from app.intelligence.market_runtime.abstention.edge_survival_monitor import EdgeHealth
from app.execution.risk_pressure_engine import compute_risk_pressure
from app.execution.exposure_constraints import apply_exposure_constraints
from app.execution.survival_scaling import compute_survival_scaling
from app.intelligence.market_runtime.calibration.probability_calibrator import calibrate_participation_quality_probability
from app.intelligence.market_runtime.calibration.brier_score_runtime import compute_brier_score_runtime


@dataclass
class AllocationResult:
    market_quality_score: float
    participation_quality_probability: float
    runtime_stability_score: float
    governance_pressure: float
    abstention_pressure: float
    position_limit: float
    risk_pressure: float
    exposure_state: str
    allocation_reason: str
    risk_units: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _believability_buckets(believability: float) -> float:
    if believability > 0.85:
        return 1.0
    if believability > 0.70:
        return 0.5
    if believability >= 0.50:
        return 0.25
    return 0.0


def allocate_capital(
    gov: GovernanceDecision,
    abstention: AbstentionDecision,
    market: MarketStructureState,
    edges: EdgeLayerResult,
    fingerprint: dict[str, float] | None = None,
    health: EdgeHealth | None = None,
    believability: float | None = None,
    rolling_dd: float = 0.0,
    open_positions: int = 0,
    execution_health: float = 1.0,
    governance_pressure: float = 0.0,
    abstention_pressure: float = 0.0,
    bar_count: int = 0,
) -> AllocationResult:
    fp = fingerprint or {}
    bel = believability if believability is not None else compute_runtime_believability(edges, fp, health)
    risk = compute_risk_pressure(gov, abstention, market)

    market_quality_score = round(market.structure_confidence, 4)
    runtime_stability_score = round(abstention.runtime_trust_score, 4)
    brier = compute_brier_score_runtime(market.structure_confidence, edges.environment_quality)
    participation_quality_probability = calibrate_participation_quality_probability(
        edges.environment_quality, bar_count, brier
    )

    survival = compute_survival_scaling(
        abstention.runtime_trust_score, health, rolling_dd, abstention_pressure
    )

    if bel < 0.50 or not gov.approved:
        return AllocationResult(
            market_quality_score=market_quality_score,
            participation_quality_probability=participation_quality_probability,
            runtime_stability_score=runtime_stability_score,
            governance_pressure=governance_pressure,
            abstention_pressure=abstention_pressure,
            position_limit=0.0,
            risk_pressure=1.0,
            exposure_state="locked",
            allocation_reason="believability_or_governance_floor",
        )

    if rolling_dd > 0.08 or abstention.abstain:
        return AllocationResult(
            market_quality_score=market_quality_score,
            participation_quality_probability=participation_quality_probability,
            runtime_stability_score=runtime_stability_score,
            governance_pressure=governance_pressure,
            abstention_pressure=abstention_pressure,
            position_limit=0.0,
            risk_pressure=1.0,
            exposure_state="locked",
            allocation_reason="dd_or_abstention_cap",
        )

    base = _believability_buckets(bel)
    pressure = 1.0
    if market.synthetic_similarity > 0.95:
        pressure *= 0.5
    elif market.synthetic_similarity > 0.90:
        pressure *= 0.75
    if market.instability_score > 0.70:
        pressure *= 0.5

    risk_units = base * gov.position_limit * pressure * execution_health * survival
    risk_units *= abstention.participation_scale
    risk_units = float(max(0.0, min(1.0, risk_units)))

    exposure = apply_exposure_constraints(risk_units, open_positions, rolling_dd)
    final_limit = exposure.max_position_limit if gov.approved and not abstention.abstain else 0.0
    if risk_units < 0.1:
        final_limit = 0.0
        reason = "risk_too_small_after_pressure"
    else:
        reason = f"bel={bel:.2f} survival={survival:.2f} gov_p={governance_pressure:.2f}"

    logger.info(f"[CapitalAllocator] limit={final_limit:.2f} units={risk_units:.2f} | {reason}")

    return AllocationResult(
        market_quality_score=market_quality_score,
        participation_quality_probability=participation_quality_probability,
        runtime_stability_score=runtime_stability_score,
        governance_pressure=round(governance_pressure, 4),
        abstention_pressure=round(abstention_pressure, 4),
        position_limit=round(final_limit, 4),
        risk_pressure=round(risk.risk_pressure, 4),
        exposure_state=exposure.exposure_state,
        allocation_reason=reason,
        risk_units=round(risk_units, 4),
    )
