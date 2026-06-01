"""Fill quality monitor — volume participation proxy."""
from __future__ import annotations

import pandas as pd


def check_fill_quality(df: pd.DataFrame) -> tuple[bool, str]:
    vol = df.get("volume")
    if vol is None or vol.sum() <= 0:
        return True, "volume_not_available"
    recent = float(vol.tail(5).mean())
    baseline = float(vol.tail(50).mean())
    if baseline <= 0:
        return True, "volume_baseline_zero"
    ratio = recent / baseline
    if ratio < 0.15:
        return False, f"fill_degradation_vol_ratio={ratio:.2f}"
    return True, "fill_ok"
