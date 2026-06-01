"""
Public API entry — delegates to sole execution pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from app.execution.pipeline import run_execution_pipeline
from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.governance.runtime_constitution.governance_engine import GovernanceDecision
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.abstention.adaptive_abstention import AbstentionDecision
from app.execution.capital_allocator import AllocationResult
from app.intelligence.brain2.models import Brain2CognitionState
from app.runtime.runtime_health import RuntimeHealth


@dataclass
class RuntimeDecision:
    symbol: str
    timestamp: str
    price: float
    context: ContextState
    market_audit: MarketStructureState
    governance: GovernanceDecision
    regime: str
    approved: bool
    direction: str
    risk_mode: str
    position_limit: float
    governance_reason: str
    edges: EdgeLayerResult | None = None
    abstention: AbstentionDecision | None = None
    allocation: AllocationResult | None = None
    runtime_health: RuntimeHealth | None = None
    runtime_metrics: dict[str, Any] | None = None
    market_environment: dict[str, Any] | None = None
    final_execution_reason: str = ""
    replay_validation: dict[str, Any] | None = None
    brain2_cognition: dict[str, Any] | None = None

    def to_api_response(self, **extra) -> dict[str, Any]:
        gov = self.governance
        resp = {
            "symbol": self.symbol,
            "direction": self.direction,
            "price": self.price,
            "timestamp": self.timestamp,
            "approved": self.approved,
            "risk_mode": _map_risk_mode_api(gov.risk_mode),
            "regime": self.regime,
            "governance": {
                "approved": gov.approved,
                "verdict": gov.verdict.value,
                "risk_mode": _map_risk_mode_api(gov.risk_mode),
                "reason": gov.reason,
                "structure_confidence": self.market_audit.structure_confidence,
                "position_scale": self.position_limit,
                "position_limit": self.position_limit,
                "governance_pressure": gov.governance_pressure,
            },
            "news_context": self.context.to_dict(),
            "market_audit": self.market_audit.to_dict(),
            "governance_decision": gov.to_dict(),
            "architecture": "amro_consolidated_runtime_v8_brain2",
            "runtime_metrics": self.runtime_metrics or {},
            "market_environment": self.market_environment or {},
            "final_execution_reason": self.final_execution_reason,
        }
        if self.edges:
            resp["behavioral_edges"] = self.edges.to_dict()
        if self.abstention:
            resp["abstention"] = self.abstention.to_dict()
        if self.allocation:
            resp["allocation"] = self.allocation.to_dict()
        if self.runtime_health:
            resp["runtime_state"] = self.runtime_health.to_dict()
        if self.replay_validation:
            resp["replay_validation"] = self.replay_validation
        if self.brain2_cognition:
            resp["brain2_cognition"] = self.brain2_cognition
        resp.update(extra)
        return resp


def _map_risk_mode_api(mode: str) -> str:
    m = (mode or "").lower()
    if m == "blocked":
        return "NO_TRADE"
    if m == "reduced":
        return "DEFENSIVE"
    return "NORMAL"


def run_runtime(
    symbol: str,
    interval: str = "1h",
    days: int = 30,
    run_context_llm: bool = True,
    log_decision: bool = True,
    df: pd.DataFrame | None = None,
    publish_to_ea: bool = True,
) -> RuntimeDecision | None:
    result = run_execution_pipeline(
        symbol=symbol,
        interval=interval,
        days=days,
        run_context_llm=run_context_llm,
        log_decision=log_decision,
        df=df,
        publish_to_ea=publish_to_ea,
    )
    if result is None:
        return None

    gov = result["governance"]
    risk_mode = _map_risk_mode_api(gov.risk_mode)
    if not result["approved"]:
        risk_mode = "NO_TRADE"

    return RuntimeDecision(
        symbol=result["symbol"],
        timestamp=result["timestamp"],
        price=result["price"],
        context=result["context"],
        market_audit=result["market_audit"],
        governance=gov,
        regime=result["regime"].regime,
        approved=result["approved"],
        direction=result["direction"],
        risk_mode=risk_mode,
        position_limit=result["position_limit"],
        governance_reason=gov.reason,
        edges=result["edges"],
        abstention=result["abstention"],
        allocation=result["allocation"],
        runtime_health=result["runtime_health"],
        runtime_metrics=result["runtime_metrics"],
        market_environment=result.get("market_environment"),
        final_execution_reason=result["final_execution_reason"],
        replay_validation=result.get("replay_validation"),
        brain2_cognition=result.get("brain2_cognition"),
    )
