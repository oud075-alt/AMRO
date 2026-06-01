"""
AMRO — AI #1: Context / News Intelligence
Observes news and macro context only. No trade entry, no BUY/SELL.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from loguru import logger

from app.intelligence import brain_stack
from app.intelligence.finnhub_client import fetch_finnhub_intelligence, format_for_brain1
from app.intelligence.gemini_agent import run_gemini_intelligence, IntelligenceReport


@dataclass
class ContextIntelligence:
    asset: str
    news_bias: str  # bullish | bearish | neutral
    event_risk: float
    confidence: float
    summary: str
    market_context: str
    invalidate_trade: bool
    raw_intel: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "asset": self.asset,
            "news_bias": self.news_bias,
            "event_risk": self.event_risk,
            "confidence": self.confidence,
            "summary": self.summary,
            "market_context": self.market_context,
            "invalidate_trade": self.invalidate_trade,
        }


def _map_sentiment_to_bias(sentiment: str) -> str:
    s = (sentiment or "").upper()
    if "BULL" in s:
        return "bullish"
    if "BEAR" in s:
        return "bearish"
    return "neutral"


def _event_risk_from_intel(intel: IntelligenceReport) -> float:
    risk = (intel.risk_level or "MEDIUM").upper()
    base = {"LOW": 0.2, "MEDIUM": 0.45, "HIGH": 0.75}.get(risk, 0.5)
    if intel.news_relevance_level == "HIGH":
        base = min(1.0, base + 0.15)
    if intel.reaction_persistence == "UNLIKELY":
        base = min(1.0, base + 0.1)
    return round(base, 4)


def _confidence_from_intel(intel: IntelligenceReport) -> float:
    q = (intel.intelligence_quality or "PARTIAL").upper()
    base = {"FULL": 0.85, "PARTIAL": 0.55, "DEGRADED": 0.25}.get(q, 0.4)
    return round(min(1.0, max(0.0, base)), 4)


def _should_invalidate(intel: IntelligenceReport, event_risk: float) -> bool:
    if event_risk >= 0.85:
        return True
    if intel.risk_level == "HIGH" and intel.news_relevance_level == "HIGH":
        return True
    return False


def run_context_intelligence(symbol: str) -> ContextIntelligence:
    """
    AI #1 — context only. Fail closed on missing/invalid LLM output.
    """
    asset = symbol.replace("=X", "").replace("/", "")
    if not brain_stack.brain1_active():
        logger.warning("[AI#1] No API key — fail closed")
        return ContextIntelligence(
            asset=asset,
            news_bias="neutral",
            event_risk=1.0,
            confidence=0.0,
            summary="Context intelligence unavailable (no API key).",
            market_context="No news context loaded.",
            invalidate_trade=True,
            error="no_api_key",
        )

    try:
        finnhub = fetch_finnhub_intelligence(symbol)
        news_text = format_for_brain1(finnhub) if finnhub.available else ""
        intel: IntelligenceReport = run_gemini_intelligence(symbol, real_news_text=news_text)

        bias = _map_sentiment_to_bias(intel.sentiment_direction)
        event_risk = _event_risk_from_intel(intel)
        confidence = _confidence_from_intel(intel)
        invalidate = _should_invalidate(intel, event_risk)

        observations = intel.observations or []
        ctx_lines = intel.market_context or []
        summary = intel.news_relevance_desc or (
            "; ".join(observations[:3]) if observations else "No material news context."
        )
        market_context = (
            " | ".join(ctx_lines[:4])
            if ctx_lines
            else intel.news_relevance_desc or "Macro context inconclusive."
        )

        return ContextIntelligence(
            asset=asset,
            news_bias=bias,
            event_risk=event_risk,
            confidence=confidence,
            summary=summary[:500],
            market_context=market_context[:500],
            invalidate_trade=invalidate,
            raw_intel={
                "sentiment_direction": intel.sentiment_direction,
                "risk_level": intel.risk_level,
                "key_events": intel.key_events,
                "uncertainties": intel.uncertainties,
            },
        )
    except (json.JSONDecodeError, KeyError, TypeError) as e:
        logger.error(f"[AI#1] Malformed intelligence: {e}")
        return _fail_closed(asset, f"malformed_response: {e}")
    except Exception as e:
        logger.error(f"[AI#1] Error: {e}")
        return _fail_closed(asset, str(e))


def _fail_closed(asset: str, reason: str) -> ContextIntelligence:
    return ContextIntelligence(
        asset=asset,
        news_bias="neutral",
        event_risk=1.0,
        confidence=0.0,
        summary="Context intelligence failed — trading blocked.",
        market_context=reason,
        invalidate_trade=True,
        error=reason,
    )
