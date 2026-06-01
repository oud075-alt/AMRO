"""Behavioral fingerprint engine — probabilistic, degradable (USDJPY port)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from app.intelligence.market_runtime.edge_lab._session import asia_mask, london_mask, enrich_market_df


def _neutral_fingerprint() -> dict[str, float]:
    return {
        "volatility_asymmetry": 1.0,
        "session_imbalance": 0.0,
        "directional_persistence_burst": 0.0,
        "liquidity_stress": 1.0,
        "expansion_decay": 1.0,
        "reaction_asymmetry": 0.0,
        "compression_persistence": 0.5,
    }


def compute_fingerprint(df: pd.DataFrame, i: int | None = None, window: int = 48) -> dict[str, float]:
    enriched = enrich_market_df(df) if "atr" not in df.columns else df.copy()
    if i is None:
        i = len(enriched) - 1
    if i < window + 5:
        return _neutral_fingerprint()

    sl = enriched.iloc[i - window : i + 1]
    close = sl["close"].values
    rets = np.diff(close) / close[:-1]
    atr = float(enriched["atr"].iloc[i]) if "atr" in enriched.columns else np.nan
    atr_hist = enriched["atr"].iloc[i - window : i].dropna()
    rng = (sl["high"] - sl["low"]) / sl["close"]

    up = rets[rets > 0]
    dn = rets[rets < 0]
    vol_asym = float(up.std() / (dn.std() + 1e-10)) if len(up) > 2 and len(dn) > 2 else 1.0

    asia = asia_mask(enriched).iloc[i - window : i + 1]
    london = london_mask(enriched).iloc[i - window : i + 1]
    asia_ret = float(sl.loc[asia, "close"].pct_change().sum()) if asia.sum() > 2 else 0.0
    lon_ret = float(sl.loc[london, "close"].pct_change().sum()) if london.sum() > 2 else 0.0
    session_imbalance = float(np.clip(lon_ret - asia_ret, -0.02, 0.02) * 50)

    sign = np.sign(rets)
    runs = max_run = 1
    cur = 1
    for j in range(1, len(sign)):
        if sign[j] == sign[j - 1] and sign[j] != 0:
            cur += 1
            max_run = max(max_run, cur)
        else:
            cur = 1
    persistence_burst = float(max_run / max(len(rets), 1))

    spread_stress = float(rng.iloc[-5:].mean() / (rng.iloc[:-5].mean() + 1e-10))
    expansion_decay = float(atr / (atr_hist.mean() + 1e-10)) if len(atr_hist) else 1.0
    reaction_asym = float(
        np.mean(rets[-3:][rets[-3:] > 0]) - np.mean(np.abs(rets[-3:][rets[-3:] < 0]))
        if len(rets) >= 3
        else 0.0
    )
    compression_persist = float(
        1.0 - atr / (atr_hist.quantile(0.75) + 1e-10) if len(atr_hist) > 10 else 0.5
    )

    return {
        "volatility_asymmetry": float(np.clip(vol_asym, 0.2, 3.0)),
        "session_imbalance": float(np.clip(session_imbalance, -1, 1)),
        "directional_persistence_burst": float(np.clip(persistence_burst, 0, 1)),
        "liquidity_stress": float(np.clip(spread_stress, 0.5, 3.0)),
        "expansion_decay": float(np.clip(expansion_decay, 0.3, 2.5)),
        "reaction_asymmetry": float(np.clip(reaction_asym * 100, -1, 1)),
        "compression_persistence": float(np.clip(compression_persist, 0, 1)),
    }


def structure_quality_from_fingerprint(fp: dict[str, float]) -> float:
    return float(
        np.clip(
            0.25 * fp.get("compression_persistence", 0.5)
            + 0.25 * (1.0 - abs(fp.get("session_imbalance", 0)))
            + 0.25 * min(1.0, fp.get("expansion_decay", 1.0) / 2.0)
            + 0.25 * min(1.0, fp.get("liquidity_stress", 1.0) / 2.0),
            0,
            1,
        )
    )
