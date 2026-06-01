"""
Statistical audit computation — AI #2 structure layer only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass
from scipy import stats
from loguru import logger


@dataclass
class AuditResult:
    structure_confidence: float
    instability_score: float
    entropy_score: float
    synthetic_similarity: float
    volatility_coherence: float
    distribution_shift: float
    signal_reliability: float
    notes: list[str]


def _instability_score(returns: np.ndarray, atr_pct: float) -> float:
    if len(returns) < 30:
        return 0.5
    z = abs(stats.skew(returns))
    k = abs(stats.kurtosis(returns, fisher=True))
    score = 0.3 * atr_pct + 0.2 * min(z, 3) / 3 + 0.2 * min(k, 10) / 10
    return float(np.clip(score, 0, 1))


def _entropy_proxy(returns: np.ndarray, window: int = 60) -> float:
    if len(returns) < window:
        return 0.5
    r = returns[-window:]
    hist, _ = np.histogram(r, bins=15, density=True)
    hp = hist[hist > 0]
    if len(hp) < 2:
        return 0.5
    ent = stats.entropy(hp, base=2) / np.log2(15)
    return float(np.clip(ent, 0, 1))


def compute_audit(
    df: pd.DataFrame,
    train_returns: np.ndarray | None = None,
) -> AuditResult:
    notes: list[str] = []

    if df.empty or len(df) < 50:
        return AuditResult(0.0, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0, ["insufficient_data"])

    if "returns" in df.columns:
        rets = df["returns"].dropna().values
    else:
        rets = df["close"].pct_change().dropna().values

    if len(rets) < 50:
        return AuditResult(0.0, 0.5, 0.5, 0.5, 0.5, 0.0, 0.0, ["insufficient_data"])

    atr_series = (df["high"] - df["low"]).rolling(14).mean()
    last_atr = atr_series.iloc[-1]
    last_close = df["close"].iloc[-1]
    atr_pct = float(last_atr / last_close) if (not np.isnan(last_atr) and last_close > 0) else 0.001

    instability = _instability_score(rets, atr_pct * 100)
    entropy = _entropy_proxy(rets)

    rv = pd.Series(rets).rolling(20).std()
    rv_clean = rv.dropna()
    if len(rv_clean) > 5:
        cur = rv_clean.iloc[-1]
        hist = rv_clean.iloc[:-1]
        vol_coh = float(1.0 - min(1.0, abs(cur - hist.mean()) / (hist.std() + 1e-10)))
    else:
        vol_coh = 0.5
        notes.append("vol_coherence_insufficient")

    shift = 0.0
    if train_returns is not None and len(train_returns) > 100:
        try:
            _, p = stats.ks_2samp(rets[-100:], train_returns[-500:])
            shift = float(1.0 - min(1.0, p * 5))
            if shift > 0.7:
                notes.append("distribution_shift_elevated")
        except Exception:
            notes.append("ks_test_failed")
    else:
        mid = len(rets) // 2
        if mid > 50:
            try:
                _, p = stats.ks_2samp(rets[-100:], rets[:mid])
                shift = float(1.0 - min(1.0, p * 5))
                if shift > 0.7:
                    notes.append("distribution_shift_vs_self")
            except Exception:
                pass

    synth_sim = float(np.clip(0.5 * entropy + 0.5 * (1 - vol_coh), 0, 1))

    structure_conf = float(np.clip(
        0.35 * (1 - instability)
        + 0.25 * vol_coh
        + 0.20 * (1 - synth_sim)
        + 0.20 * (1 - shift),
        0, 1,
    ))

    signal_rel = float(np.clip(structure_conf * (1 - 0.5 * instability), 0, 1))

    logger.info(
        f"Audit: structure_conf={structure_conf:.3f} "
        f"instability={instability:.3f} entropy={entropy:.3f} "
        f"vol_coh={vol_coh:.3f} shift={shift:.3f}"
    )

    return AuditResult(
        structure_confidence=round(structure_conf, 4),
        instability_score=round(instability, 4),
        entropy_score=round(entropy, 4),
        synthetic_similarity=round(synth_sim, 4),
        volatility_coherence=round(vol_coh, 4),
        distribution_shift=round(shift, 4),
        signal_reliability=round(signal_rel, 4),
        notes=notes,
    )
