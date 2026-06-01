"""Slippage guard — fail closed on excessive slippage proxy."""
from __future__ import annotations

import pandas as pd


def check_slippage(df: pd.DataFrame, max_ratio: float = 3.0) -> tuple[bool, str]:
    if len(df) < 20:
        return False, "insufficient_bars_for_slippage"
    rng = (df["high"] - df["low"]) / df["close"]
    ratio = float(rng.iloc[-1] / (rng.tail(20).median() + 1e-10))
    if ratio > max_ratio:
        return False, f"slippage_spike_ratio={ratio:.2f}"
    return True, "slippage_ok"
