"""Session helpers + market enrichment — ported from USDJPY amro_live/edge_lab/_session.py"""
from __future__ import annotations

import numpy as np
import pandas as pd


def hour_utc(ts) -> int:
    t = pd.Timestamp(ts)
    if t.tzinfo is None:
        t = t.tz_localize("UTC")
    else:
        t = t.tz_convert("UTC")
    return int(t.hour)


def session_mask(df: pd.DataFrame, start_h: int, end_h: int) -> pd.Series:
    h = pd.to_datetime(df["timestamp"], utc=True).dt.hour
    if start_h <= end_h:
        return (h >= start_h) & (h < end_h)
    return (h >= start_h) | (h < end_h)


def asia_mask(df: pd.DataFrame) -> pd.Series:
    return session_mask(df, 0, 8)


def london_mask(df: pd.DataFrame) -> pd.Series:
    return session_mask(df, 7, 16)


def atr_series(df: pd.DataFrame, n: int = 14) -> pd.Series:
    hl = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift(1)).abs()
    lpc = (df["low"] - df["close"].shift(1)).abs()
    tr = np.maximum(hl.values, np.maximum(hpc.values, lpc.values))
    return pd.Series(tr, index=df.index).rolling(n).mean()


def enrich_market_df(df: pd.DataFrame) -> pd.DataFrame:
    """Add columns used by edges/audit — call once per dataframe."""
    out = df.copy()
    if "timestamp" not in out.columns:
        out = out.reset_index()
        idx_name = out.columns[0]
        if idx_name != "timestamp":
            out = out.rename(columns={idx_name: "timestamp"})

    if "returns" not in out.columns:
        out["returns"] = out["close"].pct_change()
    if "volume" not in out.columns:
        out["volume"] = out.get("tick_volume", 1)
    out["atr"] = atr_series(out)
    out["atr_pct"] = out["atr"] / out["close"]
    out["rng"] = (out["high"] - out["low"]) / out["close"]
    out["hour"] = pd.to_datetime(out["timestamp"], utc=True).dt.hour
    out["body"] = (out["close"] - out["open"]).abs()
    return out
