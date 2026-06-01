"""Regime runtime — descriptive only, no trade direction."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import pandas as pd

from app.intelligence.regime_detector import detect_regime


@dataclass
class RegimeRuntime:
    regime: str
    confidence: float
    description: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_regime(df: pd.DataFrame) -> RegimeRuntime:
    r = detect_regime(df)
    return RegimeRuntime(
        regime=r.regime,
        confidence=round(r.confidence, 4),
        description=r.description or "",
    )
