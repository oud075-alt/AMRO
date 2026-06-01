"""
Market environment card — runtime participation guidance for audit UI.
Pressure values are behavioral environment readings, not outcome probabilities.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd

from app.governance.runtime_constitution.governance_engine import GovernanceDecision, RuntimeVerdict
from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.abstention.adaptive_abstention import AbstentionDecision
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState


@dataclass
class MarketEnvironmentCard:
    upside_pressure_pct: int
    downside_pressure_pct: int
    governance_status: str
    risk_level: str
    risk_warning: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_VERDICT_UI = {
    RuntimeVerdict.ALLOW: "ALLOWED",
    RuntimeVerdict.LIMIT: "LIMITED",
    RuntimeVerdict.ABSTAIN: "ABSTAIN",
    RuntimeVerdict.BLOCK: "BLOCKED",
    RuntimeVerdict.DISABLE: "DISABLED",
}


def _clip_pct(v: float) -> int:
    return int(np.clip(round(v), 0, 100))


def _environment_pressure(df: pd.DataFrame, regime: str, market: MarketStructureState, edges: EdgeLayerResult) -> tuple[int, int]:
    close = df["close"]
    upside = 50.0
    downside = 50.0

    if len(close) >= 20:
        ret10 = float((close.iloc[-1] - close.iloc[-10]) / close.iloc[-10])
        upside += ret10 * 180.0
        downside -= ret10 * 180.0

        window = close.tail(20)
        lo, hi = float(window.min()), float(window.max())
        if hi > lo:
            pos = (float(close.iloc[-1]) - lo) / (hi - lo)
            upside += (pos - 0.5) * 24.0
            downside += (0.5 - pos) * 24.0

    regime_adj = {
        "TRENDING_UP": (14.0, -10.0),
        "TRENDING_DOWN": (-10.0, 14.0),
        "BREAKOUT": (6.0, 6.0),
        "VOLATILE": (-8.0, -8.0),
        "RANGING": (0.0, 0.0),
    }
    rb, rs = regime_adj.get(regime, (0.0, 0.0))
    upside += rb
    downside += rs

    clarity = float(np.clip(edges.environment_quality * 0.45 + market.structure_confidence * 0.55, 0.15, 1.0))
    upside = 50.0 + (upside - 50.0) * clarity
    downside = 50.0 + (downside - 50.0) * clarity

    return _clip_pct(upside), _clip_pct(downside)


def _risk_level(
    market: MarketStructureState,
    gov: GovernanceDecision,
    abstention: AbstentionDecision,
    context: ContextState,
) -> str:
    if gov.verdict == RuntimeVerdict.DISABLE:
        return "Critical"
    pressure = (
        gov.governance_pressure
        + abstention.abstention_pressure
        + market.instability_score * 0.6
        + context.event_risk * 0.35
    )
    if gov.verdict == RuntimeVerdict.BLOCK or not market.tradable:
        return "High"
    if pressure >= 1.75 or market.market_state == "chaotic":
        return "Critical"
    if pressure >= 1.15 or market.instability_score > 0.65:
        return "High"
    if pressure >= 0.65 or abstention.abstain:
        return "Elevated"
    if pressure >= 0.35:
        return "Moderate"
    return "Low"


def _risk_warning(
    df: pd.DataFrame,
    market: MarketStructureState,
    gov: GovernanceDecision,
    abstention: AbstentionDecision,
    edges: EdgeLayerResult,
    context: ContextState,
) -> str:
    warnings: list[str] = []

    if market.instability_score > 0.55:
        warnings.append("volatility instability detected")
    if market.entropy_score > 0.72:
        warnings.append("unstable market participation conditions")
    if market.distribution_shift > 0.65:
        warnings.append("breakout reliability degraded")
    if market.synthetic_similarity > 0.78:
        warnings.append("liquidity sweep behavior detected")

    if len(df) >= 20:
        rng = (df["high"] - df["low"]) / df["close"]
        if float(rng.iloc[-1]) > float(rng.tail(20).median()) * 2.5:
            warnings.append("spread expansion risk elevated")

    if edges.environment_quality < 0.35:
        warnings.append("unstable market participation conditions")
    if not edges.dominant_edge:
        warnings.append("structure weakening near resistance")

    reason_l = (abstention.abstention_reason or "").lower()
    if "entropy" in reason_l:
        warnings.append("volatility instability detected")
    if "drawdown" in reason_l:
            warnings.append("wrong-timing participation risk elevated")
    if "synthetic" in reason_l:
        warnings.append("liquidity sweep behavior detected")
    if "no_behavioral" in reason_l:
        warnings.append("market environment lacks directional clarity")

    if context.event_risk > 0.7:
        warnings.append("reversal pressure increasing")
    if context.invalidate_trade:
        warnings.append("unstable market participation conditions")

    if gov.verdict in (RuntimeVerdict.BLOCK, RuntimeVerdict.DISABLE):
        if market.market_state in ("chaotic", "dead"):
            warnings.append("unstable market participation conditions")
        elif market.distribution_shift > 0.7:
            warnings.append("breakout reliability degraded")
        else:
            warnings.append("unstable market participation conditions")

    if not warnings:
        if abstention.abstain:
            return "participation conditions below runtime threshold"
        return "no elevated structural hazards detected at current bar"

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for w in warnings:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[0]


def compute_market_environment_card(
    df: pd.DataFrame,
    market: MarketStructureState,
    gov: GovernanceDecision,
    abstention: AbstentionDecision,
    edges: EdgeLayerResult,
    context: ContextState,
    regime: str,
) -> MarketEnvironmentCard:
    upside_pct, downside_pct = _environment_pressure(df, regime, market, edges)
    return MarketEnvironmentCard(
        upside_pressure_pct=upside_pct,
        downside_pressure_pct=downside_pct,
        governance_status=_VERDICT_UI.get(gov.verdict, "BLOCKED"),
        risk_level=_risk_level(market, gov, abstention, context),
        risk_warning=_risk_warning(df, market, gov, abstention, edges, context),
    )
