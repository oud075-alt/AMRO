"""Bar-level microstructure proxies — measurable, not order-book fantasy."""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class MicrostructureGrounding:
    amihud_proxy: float
    signed_pressure: float
    volume_return_asymmetry: float
    vol_liquidity_elasticity: float
    continuation_resiliency: float
    spread_proxy: float
    fill_vol_ratio: float
    amihud_rolling: float = 0.0
    amihud_zscore: float = 0.0
    vol_adjusted_impact: float = 0.0
    signed_pressure_imbalance: float = 0.0
    instability_acceleration: float = 0.0
    liquidity_elasticity: float = 0.0
    impact_stress: float = 0.0
    rolling_telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        d = {k: round(v, 6) if isinstance(v, float) else v for k, v in asdict(self).items()}
        return d


def compute_microstructure(df: pd.DataFrame) -> MicrostructureGrounding:
    if len(df) < 30:
        return MicrostructureGrounding(0.0, 0.0, 0.5, 0.0, 0.5, 0.0, 1.0)

    bar_hours = 1.0
    if len(df) >= 2:
        bar_hours = max(1.0, (df.index[-1] - df.index[-2]).total_seconds() / 3600.0)
    daily_bar = bar_hours >= 12.0
    amihud_impact_scale = 1e4 if daily_bar else 1e6

    close = df["close"].astype(float)
    rets = close.pct_change().fillna(0.0)
    vol = df.get("volume")
    no_real_volume = vol is None or float(vol.sum()) <= 0
    if no_real_volume:
        vol_s = pd.Series(1.0, index=df.index)
    else:
        vol_s = vol.astype(float).replace(0, np.nan).fillna(1.0)

    abs_r = rets.abs()
    amihud_series = abs_r / vol_s
    tail = slice(-20, None)
    amihud = float(amihud_series.iloc[tail].mean())
    amihud_baseline = float(amihud_series.iloc[-60:-20].mean()) if len(df) >= 60 else amihud
    amihud_std = float(amihud_series.iloc[-60:].std()) if len(df) >= 60 else amihud * 0.5 + 1e-12
    amihud_z = float((amihud - amihud_baseline) / (amihud_std + 1e-12))

    signed = rets.iloc[tail] * np.sign(rets.iloc[tail]) * vol_s.iloc[tail]
    signed_pressure = float(np.tanh(signed.sum() / (vol_s.iloc[tail].sum() + 1e-10)))
    signed_imbalance = float(abs(signed_pressure))

    up_mask = rets.iloc[tail] > 0
    down_mask = rets.iloc[tail] < 0
    up_vol = float(vol_s.iloc[tail][up_mask].sum())
    down_vol = float(vol_s.iloc[tail][down_mask].sum())
    total = up_vol + down_vol + 1e-10
    asym = float(abs(up_vol - down_vol) / total)

    rng = ((df["high"] - df["low"]) / close).astype(float)
    spread_proxy = float(rng.iloc[-1])
    vol_recent = float(vol_s.iloc[tail].mean())
    vol_base = float(vol_s.iloc[-50:-20].mean()) if len(df) >= 50 else vol_recent
    vol_liq_elastic = float(
        np.clip((spread_proxy / (rng.tail(50).median() + 1e-10)) / (vol_recent / (vol_base + 1e-10) + 1e-10) - 1.0, -1, 2)
    )
    liquidity_elasticity = vol_liq_elastic

    short_vol = float(rets.tail(5).std())
    mid_vol = float(rets.tail(20).std())
    long_vol = float(rets.tail(50).std()) if len(rets) >= 50 else mid_vol
    instability_accel = float(np.clip((short_vol - mid_vol) / (long_vol + 1e-10), -1, 2))

    vol_regime = short_vol / (long_vol + 1e-10)
    vol_adjusted_impact = float(amihud * (1.0 + max(0.0, vol_regime - 1.0) * 0.5))

    roll_low = close.rolling(10, min_periods=5).min()
    down_bars = rets.iloc[tail] < 0
    if down_bars.any():
        held = (close.iloc[tail][down_bars] >= roll_low.iloc[tail][down_bars] * 0.998).mean()
        resiliency = float(held)
    else:
        resiliency = 0.55

    fill_ratio = vol_recent / (vol_base + 1e-10)

    impact_stress = min(
        1.0,
        max(0.0, amihud_z * 0.15)
        + max(0.0, vol_adjusted_impact * amihud_impact_scale * 0.08)
        + max(0.0, instability_accel * 0.25)
        + max(0.0, (0.5 - resiliency) * 0.35)
        + max(0.0, (0.45 - fill_ratio) * 0.4),
    )
    if no_real_volume:
        impact_stress = min(impact_stress, spread_proxy * 8.0 + instability_accel * 0.15)

    rolling = {
        "amihud_last5": [round(float(x), 8) for x in amihud_series.tail(5).tolist()],
        "impact_stress_last5": [],
        "instability_accel": round(instability_accel, 4),
        "vol_adjusted_impact": round(vol_adjusted_impact, 8),
    }
    for i in range(5, 0, -1):
        w = amihud_series.tail(i).mean()
        rolling["impact_stress_last5"].append(
            round(min(1.0, float(w) * amihud_impact_scale * 0.05 + instability_accel * 0.2), 4)
        )

    return MicrostructureGrounding(
        amihud_proxy=amihud,
        signed_pressure=signed_pressure,
        volume_return_asymmetry=asym,
        vol_liquidity_elasticity=vol_liq_elastic,
        continuation_resiliency=resiliency,
        spread_proxy=spread_proxy,
        fill_vol_ratio=fill_ratio,
        amihud_rolling=amihud,
        amihud_zscore=amihud_z,
        vol_adjusted_impact=vol_adjusted_impact,
        signed_pressure_imbalance=signed_imbalance,
        instability_acceleration=instability_accel,
        liquidity_elasticity=liquidity_elasticity,
        impact_stress=impact_stress,
        rolling_telemetry=rolling,
    )


def impact_telemetry_penalty(micro: MicrostructureGrounding) -> float:
    """Direct feed for confidence / contra / execution fragility / replay distrust."""
    return min(
        0.45,
        micro.impact_stress * 0.35
        + max(0.0, micro.amihud_zscore) * 0.08
        + max(0.0, micro.instability_acceleration) * 0.12
        + max(0.0, micro.signed_pressure_imbalance - 0.5) * 0.1,
    )
