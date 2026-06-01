"""
AI #1 — ContextState (advisory only).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.intelligence.context_intelligence import (
    ContextIntelligence,
    run_context_intelligence,
)


@dataclass
class ContextState:
    asset: str
    event_risk: float
    summary: str
    market_context: str
    invalidate_trade: bool
    warnings: list[str]
    raw_intel: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "event_risk": self.event_risk,
            "summary": self.summary,
            "market_context": self.market_context,
            "invalidate_trade": self.invalidate_trade,
            "warnings": self.warnings,
            "error": self.error,
        }


def _from_intel(ci: ContextIntelligence) -> ContextState:
    warnings: list[str] = []
    if ci.invalidate_trade:
        warnings.append("context_invalidates_participation")
    if ci.event_risk > 0.7:
        warnings.append(f"elevated_event_risk={ci.event_risk:.2f}")
    if ci.error:
        warnings.append(f"context_error={ci.error}")
    return ContextState(
        asset=ci.asset,
        event_risk=ci.event_risk,
        summary=ci.summary,
        market_context=ci.market_context,
        invalidate_trade=ci.invalidate_trade,
        warnings=warnings,
        raw_intel=ci.raw_intel,
        error=ci.error,
    )


def load_context_state(symbol: str, run_llm: bool = True) -> ContextState:
    if not run_llm:
        return ContextState(
            asset=symbol,
            event_risk=0.5,
            summary="Context LLM skipped",
            market_context="—",
            invalidate_trade=False,
            warnings=[],
        )
    return _from_intel(run_context_intelligence(symbol))
