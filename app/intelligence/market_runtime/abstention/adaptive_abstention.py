"""
Adaptive abstention — ported from USDJPY amro_live/adaptive_abstention.py
Structure-only: no LONG/SHORT. Fail closed by default.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd
from loguru import logger

from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult
from app.intelligence.market_runtime.fingerprint import (
    compute_fingerprint,
    fingerprint_alignment,
    structure_quality_from_fingerprint,
)
from app.intelligence.market_runtime.abstention.edge_survival_monitor import EdgeHealth, evaluate_edge_survival
from app.intelligence.market_runtime.abstention.edge_believability import compute_runtime_believability
from app.runtime.runtime_health import RuntimeStateLevel


@dataclass
class AbstentionDecision:
    abstain: bool
    abstention_pressure: float  # 0..1
    abstention_reason: str
    runtime_trust_score: float  # 0..1
    participation_scale: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AdaptiveAbstention:
    """Fixed thresholds from USDJPY — no OOS tuning."""

    def __init__(
        self,
        synth_hard_block: float = 0.99,
        synth_soft_block: float = 0.92,
        min_fingerprint_align: float = 0.35,
        drawdown_accel_block: float = 0.03,
        scale_floor: float = 0.1,
    ):
        self.synth_hard_block = synth_hard_block
        self.synth_soft_block = synth_soft_block
        self.min_fingerprint_align = min_fingerprint_align
        self.drawdown_accel_block = drawdown_accel_block
        self.scale_floor = scale_floor

    def decide(
        self,
        edges: EdgeLayerResult,
        market: MarketStructureState,
        fingerprint: dict[str, float],
        health: EdgeHealth | None,
        believability: float,
        drawdown_accel: float,
        runtime_level: RuntimeStateLevel,
        context: ContextState | None = None,
    ) -> AbstentionDecision:
        reasons: list[str] = []
        pressure = 0.0

        # Runtime fail-closed
        if runtime_level in (RuntimeStateLevel.UNTRUSTED, RuntimeStateLevel.DISABLED):
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=1.0,
                abstention_reason=f"runtime_{runtime_level.value}",
                runtime_trust_score=0.0,
                participation_scale=0.0,
            )

        if runtime_level == RuntimeStateLevel.DEGRADED:
            pressure += 0.2
            reasons.append("runtime_degraded")

        synth = market.synthetic_similarity
        inst = market.instability_score
        sc = market.structure_confidence

        dominant = edges.dominant_edge
        align = fingerprint_alignment(dominant, fingerprint) if dominant else 0.5

        if not dominant and edges.aggregate_quality < 0.2:
            pressure += 0.15
            reasons.append("no_behavioral_structure")

        if health and not health.enabled:
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=1.0,
                abstention_reason="edge_disabled_by_survival_monitor",
                runtime_trust_score=0.0,
                participation_scale=0.0,
            )

        if health and health.replay_mismatch:
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=1.0,
                abstention_reason="replay_mismatch",
                runtime_trust_score=0.0,
                participation_scale=0.0,
            )

        if drawdown_accel > self.drawdown_accel_block:
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=min(1.0, 0.7 + drawdown_accel * 3),
                abstention_reason=f"drawdown_acceleration={drawdown_accel:.3f}",
                runtime_trust_score=0.0,
                participation_scale=0.0,
            )

        if synth >= self.synth_hard_block and believability < 0.6:
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=0.95,
                abstention_reason="extreme_synthetic_low_believability",
                runtime_trust_score=0.05,
                participation_scale=0.0,
            )

        if align < self.min_fingerprint_align and dominant:
            return AbstentionDecision(
                abstain=True,
                abstention_pressure=0.75,
                abstention_reason=f"fingerprint_misalignment={align:.2f}",
                runtime_trust_score=0.25,
                participation_scale=0.0,
            )

        # Soft pressure accumulation (USDJPY scale reductions → pressure)
        if synth >= self.synth_soft_block:
            pressure += 0.35
            reasons.append(f"synthetic_soft={synth:.2f}")
        if inst > 0.65:
            pressure += 0.25 * inst
            reasons.append(f"instability={inst:.2f}")
        if market.entropy_score > 0.72:
            pressure += 0.15
            reasons.append(f"entropy_spike={market.entropy_score:.2f}")
        if market.volatility_coherence < 0.35:
            pressure += 0.15
            reasons.append("volatility_incoherence")
        if sc < 0.25:
            pressure += 0.25
            reasons.append(f"low_structure={sc:.2f}")
        fp_struct = structure_quality_from_fingerprint(fingerprint)
        if fp_struct < 0.30:
            pressure += 0.2
            reasons.append(f"low_fingerprint_structure={fp_struct:.2f}")

        if health and health.degradation_score > 0.08:
            pressure += min(0.3, health.degradation_score * 2)
            reasons.append("edge_degradation")

        if context and context.invalidate_trade:
            pressure += 0.4
            reasons.append("context_invalidate")
        if context and context.event_risk > 0.85:
            pressure += 0.35
            reasons.append(f"event_risk={context.event_risk:.2f}")

        pressure = min(1.0, pressure)
        trust = max(0.0, 1.0 - pressure)

        dom = next((e for e in edges.edges if e.edge_id == dominant), None) if dominant else None
        scale = dom.edge_strength if dom and dom.edge_strength > 0 else edges.aggregate_strength
        scale = max(0.25, scale) if scale > 0 else 0.25
        scale *= max(0.25, believability)
        if health:
            scale *= health.allocation_multiplier
        if synth >= self.synth_soft_block:
            scale *= 0.5
        if inst > 0.65:
            scale *= 0.5
        if sc < 0.25:
            scale *= 0.5
        scale = float(max(0.0, min(1.0, scale)))

        abstain = scale < self.scale_floor or pressure >= 0.55
        if abstain and scale >= self.scale_floor:
            reasons.append("abstention_pressure_threshold")

        reason_str = "; ".join(reasons) if reasons else "participation_acceptable"

        logger.info(
            f"[Abstention] abstain={abstain} pressure={pressure:.2f} "
            f"trust={trust:.2f} scale={scale:.2f} | {reason_str}"
        )

        return AbstentionDecision(
            abstain=abstain,
            abstention_pressure=round(pressure, 4),
            abstention_reason=reason_str,
            runtime_trust_score=round(trust, 4),
            participation_scale=round(0.0 if abstain else scale, 4),
        )


_DEFAULT = AdaptiveAbstention()


def evaluate_abstention(
    df: pd.DataFrame,
    context: ContextState,
    market: MarketStructureState,
    edges: EdgeLayerResult,
    runtime_level: RuntimeStateLevel,
    drawdown_proxy: float = 0.0,
) -> AbstentionDecision:
    fp = compute_fingerprint(df)
    health = evaluate_edge_survival(edges, market.synthetic_similarity)
    believability = compute_runtime_believability(edges, fp, health)
    return _DEFAULT.decide(
        edges=edges,
        market=market,
        fingerprint=fp,
        health=health,
        believability=believability,
        drawdown_accel=drawdown_proxy,
        runtime_level=runtime_level,
        context=context,
    )
