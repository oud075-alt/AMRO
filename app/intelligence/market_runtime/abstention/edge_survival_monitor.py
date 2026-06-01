"""Track per-edge health — ported from USDJPY amro_live/edge_survival_monitor.py"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from app.intelligence.market_runtime.edge_lab.edge_types import EdgeLayerResult, EdgeSignal


@dataclass
class EdgeHealth:
    edge: str
    enabled: bool = True
    allocation_multiplier: float = 1.0
    rolling_sharpe: float = 0.0
    rolling_expectancy: float = 0.0
    degradation_score: float = 0.0
    half_life_bars: float = 0.0
    synthetic_drift: float = 0.0
    post_cost_survival: float = 1.0
    replay_mismatch: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EdgeSurvivalMonitor:
    """Stateful edge survival — reduce allocation or disable on collapse."""

    def __init__(self, window: int = 120, disable_threshold: float = -0.5):
        self.window = window
        self.disable_threshold = disable_threshold
        self._pnl_buffer: dict[str, list[float]] = {}
        self._equity_buffer: dict[str, list[float]] = {}
        self.health: dict[str, EdgeHealth] = {}
        self._replay_signatures: dict[str, str] = {}

    def update(
        self,
        edge: str,
        bar_pnl: float,
        equity: float,
        synthetic_sim: float = 0.5,
        replay_signature: str = "",
    ) -> EdgeHealth:
        if replay_signature and edge in self._replay_signatures:
            if self._replay_signatures[edge] != replay_signature:
                h = self.health.get(edge) or EdgeHealth(edge=edge)
                h.replay_mismatch = True
                h.notes = "replay signature mismatch"
                self.health[edge] = h
        if replay_signature:
            self._replay_signatures[edge] = replay_signature

        self._pnl_buffer.setdefault(edge, []).append(bar_pnl)
        self._equity_buffer.setdefault(edge, []).append(equity)
        if len(self._pnl_buffer[edge]) > self.window:
            self._pnl_buffer[edge] = self._pnl_buffer[edge][-self.window :]
            self._equity_buffer[edge] = self._equity_buffer[edge][-self.window :]

        pnls = np.array(self._pnl_buffer[edge])
        eq = np.array(self._equity_buffer[edge])
        h = self.health.get(edge) or EdgeHealth(edge=edge)

        if len(pnls) < 20:
            h.notes = "warming"
            self.health[edge] = h
            return h

        mu = float(pnls.mean())
        sig = float(pnls.std() + 1e-10)
        h.rolling_expectancy = mu
        h.rolling_sharpe = float(mu / sig * np.sqrt(252 * 6))

        peak = np.maximum.accumulate(eq)
        dd = (eq - peak) / (peak + 1e-10)
        h.degradation_score = float(-dd.min()) if len(dd) else 0.0

        cum = np.cumsum(pnls)
        peak_cum = np.maximum.accumulate(cum)
        decay_idx = np.where(cum < peak_cum * 0.5)[0]
        h.half_life_bars = float(decay_idx[0]) if len(decay_idx) else float(self.window)

        h.synthetic_drift = synthetic_sim
        h.post_cost_survival = 1.0 if mu > 0 else max(0.0, 1.0 + mu / (sig + 1e-10))

        if h.replay_mismatch:
            h.enabled = False
            h.allocation_multiplier = 0.0
            h.notes = "replay mismatch — disabled"
        elif h.rolling_sharpe < self.disable_threshold or h.degradation_score > 0.12:
            h.enabled = False
            h.allocation_multiplier = 0.0
            h.notes = "edge collapsed — disabled"
        elif h.rolling_sharpe < 0.0:
            h.allocation_multiplier = 0.25
            h.notes = "degraded — quarter size"
        elif h.rolling_sharpe < 0.3:
            h.allocation_multiplier = 0.5
            h.notes = "weak — half size"
        else:
            h.allocation_multiplier = 1.0
            h.notes = "healthy"

        self.health[edge] = h
        return h

    def update_from_layer(self, edges: EdgeLayerResult, synthetic_sim: float) -> EdgeHealth | None:
        """Update dominant edge using structure-quality proxy PnL (live path)."""
        if not edges.dominant_edge:
            return None
        dom = next((e for e in edges.edges if e.edge_id == edges.dominant_edge), None)
        if not dom:
            return None
        bar_pnl = (dom.edge_quality * dom.edge_strength - 0.45) if dom.edge_detected else -0.02
        equity = 1.0 + bar_pnl
        return self.update(
            dom.edge_id,
            bar_pnl,
            equity,
            synthetic_sim=synthetic_sim,
            replay_signature=dom.replay_signature,
        )

    def get_health(self, edge: str) -> EdgeHealth | None:
        return self.health.get(edge)


# Process-wide survival state (replayable across pipeline ticks)
_SURVIVAL_MONITOR = EdgeSurvivalMonitor()


def get_survival_monitor() -> EdgeSurvivalMonitor:
    return _SURVIVAL_MONITOR


def evaluate_edge_survival(edges: EdgeLayerResult, synthetic_sim: float = 0.5) -> EdgeHealth | None:
    monitor = get_survival_monitor()
    return monitor.update_from_layer(edges, synthetic_sim)
