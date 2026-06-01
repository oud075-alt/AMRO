"""
AMRO — Regime Detector
ตรวจสอบ "สภาวะตลาด" ปัจจุบัน เพื่อให้บริบทแก่ Signal

Regimes:
  TRENDING_UP    — trend ขาขึ้นชัดเจน
  TRENDING_DOWN  — trend ขาลงชัดเจน
  RANGING        — ตลาด sideways / ไม่มีทิศ
  VOLATILE       — ความผันผวนสูงผิดปกติ
  BREAKOUT       — กำลัง breakout จาก range
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass
from typing import Literal
from loguru import logger


RegimeType = Literal[
    "TRENDING_UP",
    "TRENDING_DOWN",
    "RANGING",
    "VOLATILE",
    "BREAKOUT",
    "UNKNOWN"
]


@dataclass
class RegimeResult:
    regime: RegimeType
    confidence: float          # 0.0 – 1.0
    description: str           # อธิบายภาษาไทย
    metrics: dict              # ตัวเลขที่ใช้ตัดสิน
    trade_advice: str          # survival/governance guidance for this regime


def detect_regime(df: pd.DataFrame) -> RegimeResult:
    """
    วิเคราะห์ DataFrame (ต้องมี close, high, low, volume)
    แล้วจำแนก Market Regime ปัจจุบัน
    """
    if df.empty or len(df) < 50:
        return RegimeResult(
            regime="UNKNOWN",
            confidence=0.0,
            description="ข้อมูลไม่เพียงพอสำหรับการวิเคราะห์",
            metrics={},
            trade_advice="ข้อมูลไม่พอ — งด participation จนกว่า runtime จะชัดขึ้น"
        )

    close  = df["close"]
    high   = df["high"]
    low    = df["low"]
    n      = len(close)

    # ── 1. ADX: Trend Strength ───────────────────────────────
    # คำนวณ ATR manually เพื่อหลีกเลี่ยง dependency
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs()
    ], axis=1).max(axis=1)
    atr_14 = tr.rolling(14).mean().iloc[-1]
    atr_pct = atr_14 / close.iloc[-1] * 100  # % ของราคา

    # ADX ใช้วิธีง่าย: slope ของ EMA20 vs EMA50
    ema_20 = close.ewm(span=20).mean()
    ema_50 = close.ewm(span=50).mean()
    ema_200 = close.ewm(span=200).mean()

    # Trend direction
    last_ema20  = ema_20.iloc[-1]
    last_ema50  = ema_50.iloc[-1]
    last_ema200 = ema_200.iloc[-1]
    last_close  = close.iloc[-1]

    # Slope of EMA20 (normalized)
    ema20_slope = (ema_20.iloc[-1] - ema_20.iloc[-10]) / ema_20.iloc[-10] * 100

    # ── 2. Bollinger Band Width: Volatility / Squeeze ────────
    sma20     = close.rolling(20).mean()
    std20     = close.rolling(20).std()
    bb_width  = (4 * std20 / sma20 * 100).iloc[-1]  # %
    bb_width_hist = (4 * std20 / sma20 * 100).iloc[-50:]
    bb_pct_rank = (bb_width_hist < bb_width).mean()  # 0–1, สูง = volatile

    # ── 3. Price Position in Range ───────────────────────────
    recent_high = high.iloc[-20:].max()
    recent_low  = low.iloc[-20:].min()
    range_size  = recent_high - recent_low
    price_pos   = (last_close - recent_low) / range_size if range_size > 0 else 0.5

    metrics = {
        "ema20_slope_pct": round(float(ema20_slope), 3),
        "atr_pct": round(float(atr_pct), 3),
        "bb_width_pct": round(float(bb_width), 3),
        "bb_volatility_rank": round(float(bb_pct_rank), 3),
        "price_position_in_range": round(float(price_pos), 3),
        "ema20_above_ema50": bool(last_ema20 > last_ema50),
        "price_above_ema200": bool(last_close > last_ema200),
    }

    # ── 4. Classify Regime ───────────────────────────────────

    # Volatile: BB width สูงมาก
    if bb_pct_rank > 0.85 and atr_pct > 2.5:
        return RegimeResult(
            regime="VOLATILE",
            confidence=round(float(bb_pct_rank), 3),
            description=f"ความผันผวนสูงผิดปกติ (ATR {atr_pct:.1f}% ของราคา) "
                        f"BB Width อยู่ใน top {(1-bb_pct_rank)*100:.0f}% ของประวัติ",
            metrics=metrics,
            trade_advice="ลด/หลีกเลี่ยง participation | execution risk สูง | ห้ามเร่งตัดสินใจ"
        )

    # Breakout: ราคาเพิ่งทะลุ high/low ของ 20 แท่ง
    prev_high = high.iloc[-21:-1].max()
    prev_low  = low.iloc[-21:-1].min()
    if last_close > prev_high * 1.002:
        return RegimeResult(
            regime="BREAKOUT",
            confidence=0.78,
            description=f"ราคากำลัง Breakout ขึ้นเหนือ High 20 แท่ง ที่ {prev_high:.4f}",
            metrics=metrics,
            trade_advice="breakout pressure สูงขึ้น แต่ต้องรอ stability/retest confirmation ก่อนเพิ่ม risk"
        )
    if last_close < prev_low * 0.998:
        return RegimeResult(
            regime="BREAKOUT",
            confidence=0.75,
            description=f"ราคากำลัง Breakdown ต่ำกว่า Low 20 แท่ง ที่ {prev_low:.4f}",
            metrics=metrics,
            trade_advice="breakdown pressure สูงขึ้น แต่ false-break risk ยังต้องถูกกรองด้วย governance"
        )

    # Trending: EMA slope ชัดเจน
    if ema20_slope > 1.5 and last_ema20 > last_ema50:
        conf = min(0.92, 0.6 + abs(ema20_slope) / 20)
        return RegimeResult(
            regime="TRENDING_UP",
            confidence=round(conf, 3),
            description=f"Uptrend ชัดเจน | EMA20 slope +{ema20_slope:.1f}% | "
                        f"{'ราคาเหนือ EMA200' if metrics['price_above_ema200'] else 'ราคาใต้ EMA200'}",
            metrics=metrics,
            trade_advice="trend pressure ฝั่งขึ้นเด่น แต่ยังเป็น observation; ใช้ governance กรอง execution risk"
        )

    if ema20_slope < -1.5 and last_ema20 < last_ema50:
        conf = min(0.92, 0.6 + abs(ema20_slope) / 20)
        return RegimeResult(
            regime="TRENDING_DOWN",
            confidence=round(conf, 3),
            description=f"Downtrend ชัดเจน | EMA20 slope {ema20_slope:.1f}% | "
                        f"{'ราคาใต้ EMA200' if not metrics['price_above_ema200'] else 'ยัง countertrend'}",
            metrics=metrics,
            trade_advice="trend pressure ฝั่งลงเด่น แต่ยังเป็น observation; ใช้ governance กรอง execution risk"
        )

    # Default: Ranging
    return RegimeResult(
        regime="RANGING",
        confidence=round(1.0 - abs(ema20_slope) / 5, 3),
        description=f"ตลาด Sideways | Range {recent_low:.4f} – {recent_high:.4f} | "
                    f"ราคาอยู่ที่ {price_pos*100:.0f}% ของ range",
        metrics=metrics,
        trade_advice="range regime — directional certainty ต่ำ; ลด risk และรอ environment stability"
    )
