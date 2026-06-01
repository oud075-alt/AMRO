"""Spread guard — fail closed on invalid spread conditions."""
from __future__ import annotations

import pandas as pd


def check_spread(df: pd.DataFrame, max_median_mult: float = 4.0) -> tuple[bool, str]:
    if len(df) < 50:
        return False, "insufficient_bars_for_spread"
    rng = (df["high"] - df["low"]) / df["close"]
    if float(rng.iloc[-1]) > float(rng.tail(50).median()) * max_median_mult:
        return False, "spread_spike"
    return True, "spread_ok"
