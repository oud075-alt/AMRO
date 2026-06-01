"""
AI #3 — Constitutional governance engine (sole authority).
Outputs: ALLOW | LIMIT | ABSTAIN | BLOCK | DISABLE only.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any

from loguru import logger

from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.ecology.ecology_balance_audit import EcologyAudit
from app.intelligence.brain2.models import Brain2CognitionState

STRUCTURE_CONF_MIN = 0.30
SYNTHETIC_SIM_MAX = 0.80
INSTABILITY_REDUCE_ABOVE = 0.65
DISTRIBUTION_SHIFT_OFF = 0.75
RELIABILITY_MIN = 0.25
EVENT_RISK_BLOCK = 0.85
CONTRA_PRESSURE_LIMIT = 0.55
SEMANTIC_CONF_MIN = 0.25
FAKEOUT_RISK_BLOCK = 0.62
DEFENSIVE_INSTABILITY = 0.70


def _apply_brain2_advisory(
    brain2: Brain2CognitionState | None,
    scale: float,
    pressure: float,
    reduced: bool,
    blocked: bool,
    reasons: list[str],
) -> tuple[float, float, bool, bool]:
    """Brain-3 consumes Brain-2 semantics — advisory pressure only."""
    if not brain2:
        return scale, pressure, reduced, blocked

    ctx = brain2.governance_context
    if brain2.contradiction_pressure >= CONTRA_PRESSURE_LIMIT:
        scale *= max(0.35, 1.0 - brain2.contradiction_pressure * 0.45)
        pressure = min(1.0, pressure + brain2.contradiction_pressure * 0.25)
        reduced = True
        reasons.append(f"brain2_contradiction={brain2.contradiction_pressure:.2f}")

    accum = getattr(brain2, "accumulated_contradiction_pressure", 0.0) or 0.0
    if accum >= CONTRA_PRESSURE_LIMIT:
        scale *= max(0.3, 1.0 - accum * 0.5)
        pressure = min(1.0, pressure + accum * 0.3)
        reduced = True
        reasons.append(f"brain2_contra_accum={accum:.2f}")

    if brain2.instability_probability >= 0.68:
        scale *= 0.75
        pressure = min(1.0, pressure + 0.12)
        reduced = True
        reasons.append(f"brain2_instability={brain2.instability_probability:.2f}")

    if brain2.fakeout_probability >= FAKEOUT_RISK_BLOCK:
        scale *= 0.6
        reduced = True
        pressure = min(1.0, pressure + 0.15)
        reasons.append(f"brain2_fakeout={brain2.fakeout_probability:.2f}")

    if brain2.semantic_confidence < SEMANTIC_CONF_MIN and brain2.contradiction_pressure > 0.35:
        reduced = True
        reasons.append(f"brain2_low_semantic_conf={brain2.semantic_confidence:.2f}")

    gov_conf = getattr(brain2, "governance_confidence", brain2.semantic_confidence) or 0.0
    if gov_conf < SEMANTIC_CONF_MIN and max(brain2.contradiction_pressure, getattr(brain2, "accumulated_contradiction_pressure", 0)) > 0.3:
        scale *= 0.85
        reduced = True
        reasons.append(f"brain2_low_governance_conf={gov_conf:.2f}")

    abstention_t = getattr(brain2, "abstention_tendency", 0.0) or 0.0
    if abstention_t >= 0.45:
        scale *= max(0.4, 1.0 - abstention_t * 0.55)
        pressure = min(1.0, pressure + abstention_t * 0.2)
        reduced = True
        reasons.append(f"brain2_memory_first_abstention={abstention_t:.2f}")

    if ctx and ctx.governance_implication.startswith("reduce exposure"):
        scale *= 0.8
        reduced = True
        reasons.append("brain2_gov_context_reduce_exposure")

    return scale, pressure, reduced, blocked


class RuntimeVerdict(str, Enum):
    ALLOW = "ALLOW"
    LIMIT = "LIMIT"
    ABSTAIN = "ABSTAIN"
    BLOCK = "BLOCK"
    DISABLE = "DISABLE"


@dataclass
class GovernanceDecision:
    verdict: RuntimeVerdict
    position_limit: float
    risk_mode: str
    reason: str
    governance_pressure: float

    @property
    def approved(self) -> bool:
        return self.verdict in (RuntimeVerdict.ALLOW, RuntimeVerdict.LIMIT)

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "approved": self.approved,
            "position_limit": self.position_limit,
            "risk_mode": self.risk_mode,
            "reason": self.reason,
            "governance_pressure": self.governance_pressure,
        }


def evaluate_governance(
    context: ContextState,
    market: MarketStructureState,
    edges: EdgeLayerResult | None = None,
    ecology: EcologyAudit | None = None,
    brain2: Brain2CognitionState | None = None,
) -> GovernanceDecision:
    reasons: list[str] = []
    scale = 1.0
    blocked = False
    reduced = False
    pressure = 0.0

    if edges and edges.environment_quality < 0.35:
        scale *= 0.7
        reduced = True
        pressure += 0.15
        reasons.append(f"poor_edge_environment={edges.environment_quality:.2f}")

    if ecology and not ecology.passed:
        scale *= 0.6
        reduced = True
        pressure += 0.2
        reasons.append("ecology_balance_fail")

    if context.invalidate_trade:
        blocked = True
        pressure = 1.0
        reasons.append("context_invalidate_trade")

    if context.event_risk >= EVENT_RISK_BLOCK:
        blocked = True
        pressure = 1.0
        reasons.append(f"event_risk={context.event_risk:.2f}")

    if context.error:
        blocked = True
        pressure = 1.0
        reasons.append(f"context_error={context.error}")

    if not market.tradable:
        blocked = True
        pressure = max(pressure, 0.9)
        reasons.append(f"market_not_tradable:{market.market_state}")

    if market.market_state in ("chaotic", "dead"):
        blocked = True
        reasons.append(f"market_state={market.market_state}")

    if market.structure_confidence < STRUCTURE_CONF_MIN:
        blocked = True
        reasons.append(f"low_structure_conf={market.structure_confidence:.2f}")

    if market.signal_reliability < RELIABILITY_MIN:
        blocked = True
        reasons.append(f"low_reliability={market.signal_reliability:.2f}")

    if market.distribution_shift > DISTRIBUTION_SHIFT_OFF:
        blocked = True
        reasons.append(f"distribution_shift={market.distribution_shift:.2f}")

    if market.instability_score > INSTABILITY_REDUCE_ABOVE:
        scale *= max(0.2, 1.0 - market.instability_score)
        reduced = True
        pressure += 0.15 * market.instability_score
        reasons.append(f"high_instability={market.instability_score:.2f}")

    if market.instability_score > DEFENSIVE_INSTABILITY:
        reduced = True

    if market.synthetic_similarity > SYNTHETIC_SIM_MAX:
        scale *= 0.5
        reduced = True
        pressure += 0.2
        reasons.append(f"synthetic_similarity={market.synthetic_similarity:.2f}")

    if market.market_state == "unstable":
        reduced = True
        reasons.append("unstable_market_state")

    scale, pressure, reduced, blocked = _apply_brain2_advisory(
        brain2, scale, pressure, reduced, blocked, reasons
    )

    if scale < 0.15:
        blocked = True
        reasons.append("position_limit_floor")

    pressure = min(1.0, pressure)

    if blocked:
        verdict = RuntimeVerdict.BLOCK
        risk_mode = "blocked"
        limit = 0.0
    elif reduced or scale < 1.0:
        verdict = RuntimeVerdict.LIMIT
        risk_mode = "reduced"
        limit = round(scale, 4)
    else:
        verdict = RuntimeVerdict.ALLOW
        risk_mode = "normal"
        limit = round(scale, 4)

    reason_str = "; ".join(reasons) if reasons else "ok"
    logger.info(f"[GovernanceEngine] verdict={verdict.value} limit={limit} | {reason_str}")

    return GovernanceDecision(
        verdict=verdict,
        position_limit=limit,
        risk_mode=risk_mode,
        reason=reason_str,
        governance_pressure=round(pressure, 4),
    )
