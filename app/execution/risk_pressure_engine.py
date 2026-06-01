"""Risk pressure from governance + abstention inputs only."""
from __future__ import annotations

from dataclasses import dataclass

from app.governance.runtime_constitution.governance_engine import GovernanceDecision, RuntimeVerdict
from app.intelligence.market_runtime.abstention.adaptive_abstention import AbstentionDecision
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState


@dataclass
class RiskPressure:
    risk_pressure: float
    survival_scaling: float
    governance_pressure: float


def compute_risk_pressure(
    gov: GovernanceDecision,
    abstention: AbstentionDecision,
    market: MarketStructureState,
) -> RiskPressure:
    gov_p = gov.governance_pressure
    if gov.verdict in (RuntimeVerdict.BLOCK, RuntimeVerdict.DISABLE):
        gov_p = max(gov_p, 1.0)
    elif gov.verdict == RuntimeVerdict.LIMIT:
        gov_p = max(gov_p, 0.35)

    abs_p = abstention.abstention_pressure
    inst_p = market.instability_score * 0.5
    combined = min(1.0, max(gov_p, abs_p, inst_p))
    survival_scale = max(0.1, 1.0 - combined)

    return RiskPressure(
        risk_pressure=round(combined, 4),
        survival_scaling=round(survival_scale, 4),
        governance_pressure=round(gov_p, 4),
    )
