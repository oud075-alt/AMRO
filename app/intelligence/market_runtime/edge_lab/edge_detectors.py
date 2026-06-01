"""
Behavioral edge structure detectors — ported from USDJPY amro_live/edge_lab.
Returns structure-only EdgeSignal (NO BUY/SELL / LONG/SHORT).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.intelligence.market_runtime.edge_lab._session import asia_mask, hour_utc
from app.intelligence.market_runtime.edge_lab._helpers import clip, replay_signature
from app.intelligence.market_runtime.edge_lab.edge_types import EdgeSignal


def detect_london_breakout(df: pd.DataFrame, i: int) -> EdgeSignal:
    """London compression-expansion structure after Asian range (USDJPY Edge A)."""
    edge_id = "london_breakout"
    if i < 80:
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "warmup")

    ts = df["timestamp"].iloc[i]
    h = hour_utc(ts)
    if not (7 <= h <= 11):
        return EdgeSignal(edge_id, False, 0, 0, 0, 0.5, replay_signature(edge_id, float(h)), "outside london window")

    atr = df["atr"]
    if np.isnan(atr.iloc[i]):
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "atr nan")

    asia = asia_mask(df)
    look = df.iloc[max(0, i - 32) : i]
    asia_bars = look[asia.iloc[look.index]]
    if len(asia_bars) < 4:
        return EdgeSignal(edge_id, False, 0, 0, 0, 0.6, replay_signature(edge_id, 0), "insufficient asia bars")

    asia_rng = (asia_bars["high"].max() - asia_bars["low"].min()) / asia_bars["close"].iloc[-1]
    atr_pct = float(atr.iloc[i] / df["close"].iloc[i])
    atr_ma = float(atr.iloc[i - 20 : i].mean())
    compression = asia_rng < atr_pct * 2.5
    expansion = float(atr.iloc[i]) > atr_ma * 1.08

    hi_asia = asia_bars["high"].max()
    lo_asia = asia_bars["low"].min()
    close = float(df["close"].iloc[i])
    spread_norm = (df["high"].iloc[i] - df["low"].iloc[i]) / close

    recent = df.iloc[i - 3 : i + 1]
    up_persist = (recent["close"].diff().dropna() > 0).sum() >= 2
    dn_persist = (recent["close"].diff().dropna() < 0).sum() >= 2
    persistence = up_persist or dn_persist

    break_up = close > hi_asia * 1.0001
    break_dn = close < lo_asia * 0.9999
    range_break = break_up or break_dn
    spread_ok = spread_norm > atr_pct * 0.5

    detected = compression and expansion and persistence and range_break and spread_ok
    up_mag = (close - hi_asia) / (atr.iloc[i] + 1e-10) if break_up else 0.0
    dn_mag = (lo_asia - close) / (atr.iloc[i] + 1e-10) if break_dn else 0.0
    strength = clip(min(1.0, max(up_mag, dn_mag) * 2))
    quality = clip(0.4 * strength + 0.3 * float(expansion) + 0.3 * float(compression))
    fit = clip(quality * (1.0 if compression and expansion else 0.5))

    return EdgeSignal(
        edge_id=edge_id,
        edge_detected=bool(detected),
        edge_strength=round(strength, 4),
        edge_quality=round(quality, 4),
        environment_alignment=round(fit, 4),
        confidence_decay=round(clip(0.3 + (1 - quality) * 0.5), 4),
        replay_signature=replay_signature(edge_id, asia_rng, atr_pct, strength, float(expansion)),
        description="London compression-expansion with Asian range break structure",
    )


def detect_asia_compression(df: pd.DataFrame, i: int) -> EdgeSignal:
    """Asia squeeze → delayed expansion structure (USDJPY Edge B)."""
    edge_id = "asia_compression"
    if i < 100:
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "warmup")

    h = hour_utc(df["timestamp"].iloc[i])
    if not (8 <= h <= 14):
        return EdgeSignal(edge_id, False, 0, 0, 0, 0.5, replay_signature(edge_id, float(h)), "outside post-asia window")

    atr = df["atr"]
    atr_now = float(atr.iloc[i])
    atr_hist = atr.iloc[i - 50 : i].dropna()
    if len(atr_hist) < 20 or np.isnan(atr_now):
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "atr insufficient")

    squeeze = atr_now / (atr_hist.mean() + 1e-10)
    rng = (df["high"] - df["low"]) / df["close"]
    rng_pct = float(rng.iloc[i - 50 : i].quantile(0.15))
    compressed = squeeze < 0.85 and float(rng.iloc[i - 8 : i].mean()) < rng_pct * 1.2
    expansion = atr_now > float(atr.iloc[i - 3])
    drift = abs(float(df["close"].iloc[i] - df["close"].iloc[i - 5]) / df["close"].iloc[i])

    detected = compressed and expansion and drift > 0.0008
    strength = clip(min(1.0, drift * 300))
    quality = clip(0.5 * strength + 0.5 * clip(1.0 - squeeze))
    fit = clip(quality if compressed else 0.2)

    return EdgeSignal(
        edge_id=edge_id,
        edge_detected=bool(detected),
        edge_strength=round(strength, 4),
        edge_quality=round(quality, 4),
        environment_alignment=round(fit, 4),
        confidence_decay=0.35,
        replay_signature=replay_signature(edge_id, squeeze, drift, strength),
        description="Post-Asia squeeze with delayed expansion structure",
    )


def detect_liquidity_vacuum(df: pd.DataFrame, i: int) -> EdgeSignal:
    """Liquidity vacuum — abnormal bar expansion + weak pullback (USDJPY Edge D)."""
    edge_id = "liquidity_vacuum"
    if i < 40:
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "warmup")

    atr = df["atr"]
    body = (df["close"] - df["open"]).abs()
    rng = df["high"] - df["low"]
    accel = abs(float(df["close"].iloc[i] - df["close"].iloc[i - 3]) / df["close"].iloc[i])
    bar_exp = float(rng.iloc[i] / (atr.iloc[i] + 1e-10))
    weak_pullback = float(body.iloc[i - 2 : i].mean()) < float(rng.iloc[i - 2 : i].mean()) * 0.35
    spread_instab = float(rng.iloc[i]) > float(rng.iloc[i - 20 : i].quantile(0.9))

    detected = bar_exp >= 1.4 and spread_instab and weak_pullback and accel > 0.0015
    strength = clip(min(1.0, bar_exp / 3))
    quality = clip(strength * 0.85)
    fit = clip(strength if spread_instab else 0.3)

    return EdgeSignal(
        edge_id=edge_id,
        edge_detected=bool(detected),
        edge_strength=round(strength, 4),
        edge_quality=round(quality, 4),
        environment_alignment=round(fit, 4),
        confidence_decay=0.55,
        replay_signature=replay_signature(edge_id, bar_exp, accel, strength),
        description="Thin liquidity vacuum thrust structure",
    )


def detect_volatility_exhaustion(df: pd.DataFrame, i: int) -> EdgeSignal:
    """Volatility spike + extension + decay structure (USDJPY Edge C)."""
    edge_id = "volatility_exhaustion"
    if i < 60:
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "warmup")

    atr = df["atr"]
    rets = df["close"].pct_change()
    ext = float(rets.iloc[i - 5 : i].sum())
    z = (df["close"].iloc[i] - df["close"].iloc[i - 30 : i].mean()) / (
        df["close"].iloc[i - 30 : i].std() + 1e-10
    )
    spike = float(atr.iloc[i]) > float(atr.iloc[i - 20 : i].mean()) * 1.25
    decay = float(atr.iloc[i]) < float(atr.iloc[i - 1]) * 1.02

    extension = abs(z) >= 2.0 and abs(ext) >= 0.003
    detected = spike and extension and decay
    strength = clip(min(1.0, (abs(z) - 2) / 3) if abs(z) > 2 else abs(ext) * 50)
    quality = clip(0.6 * strength + 0.4 * float(decay))
    fit = clip(quality if spike else 0.2)

    return EdgeSignal(
        edge_id=edge_id,
        edge_detected=bool(detected),
        edge_strength=round(strength, 4),
        edge_quality=round(quality, 4),
        environment_alignment=round(fit, 4),
        confidence_decay=0.45,
        replay_signature=replay_signature(edge_id, float(z), ext, strength),
        description="Post-spike extension with volatility decay structure",
    )


def detect_compression_release(df: pd.DataFrame, i: int) -> EdgeSignal:
    """
    Compression release — post-spike recoil + vol decay (adapted from USDJPY event_recoil).
    Structure-only; no directional trade output.
    """
    edge_id = "compression_release"
    if i < 50:
        return EdgeSignal(edge_id, False, 0, 0, 0, 1.0, replay_signature(edge_id, 0), "warmup")

    atr = df["atr"]
    rng = (df["high"] - df["low"]) / df["close"]
    spike_bar = float(rng.iloc[i - 1]) > float(rng.iloc[i - 30 : i - 1].quantile(0.95))
    decay = float(atr.iloc[i]) < float(atr.iloc[i - 1]) * 0.98
    prev_move = abs(float(df["close"].iloc[i - 1] - df["close"].iloc[i - 2]) / df["close"].iloc[i - 2])
    recoil = abs(float(df["close"].iloc[i] - df["close"].iloc[i - 1]) / df["close"].iloc[i - 1])

    # Also check squeeze→release coil
    squeeze = float(atr.iloc[i - 25 : i - 5].mean())
    release = float(atr.iloc[i - 3 : i + 1].mean())
    release_ratio = release / (squeeze + 1e-10)

    recoil_struct = spike_bar and decay and prev_move > 0.002 and recoil > 0.0005
    coil_release = release_ratio > 1.2 and decay
    detected = recoil_struct or coil_release

    strength = clip(min(1.0, recoil * 400) if recoil_struct else min(1.0, (release_ratio - 1.0) / 0.8))
    quality = clip(0.55 * strength + 0.45 * float(decay))
    fit = clip(quality if (spike_bar or release_ratio > 1.1) else 0.25)

    return EdgeSignal(
        edge_id=edge_id,
        edge_detected=bool(detected),
        edge_strength=round(strength, 4),
        edge_quality=round(quality, 4),
        environment_alignment=round(fit, 4),
        confidence_decay=0.4,
        replay_signature=replay_signature(edge_id, recoil, release_ratio, strength),
        description="Post-spike compression release / recoil structure",
    )


EDGE_DETECTORS = [
    detect_london_breakout,
    detect_asia_compression,
    detect_liquidity_vacuum,
    detect_volatility_exhaustion,
    detect_compression_release,
]
