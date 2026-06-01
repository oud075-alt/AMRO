"""
Brain 2 — GPT Analyst (OPENAI_API_KEY)
Probabilistic market-structure analysis only. No BUY/SELL, no execution authority.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from typing import Any

from loguru import logger
from openai import OpenAI

from app.intelligence import brain_stack
from app.intelligence.brain2.models import Brain2CognitionState
from app.intelligence.context.context_state import ContextState
from app.intelligence.market_runtime.structure.market_structure import MarketStructureState

BANNED = ("guaranteed", "certainly will", "buy now", "sell now", "must trade", "100%")


@dataclass
class Brain2AnalystReport:
    symbol: str
    analyst_summary: str
    environment_read: str
    uncertainty_note: str
    intelligence_quality: str  # FULL | PARTIAL | DEGRADED
    model: str = brain_stack.BRAIN2_MODEL
    active: bool = False
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _compact_brain2(brain2: Brain2CognitionState) -> dict[str, Any]:
    b2 = brain2.to_dict() if hasattr(brain2, "to_dict") else {}
    interpretations = b2.get("interpretations") or []
    top = sorted(
        interpretations,
        key=lambda x: float(x.get("confidence") or 0),
        reverse=True,
    )[:5]
    return {
        "regime": b2.get("regime"),
        "semantic_confidence": b2.get("semantic_confidence"),
        "governance_confidence": b2.get("governance_confidence"),
        "contradiction_pressure": b2.get("contradiction_pressure"),
        "abstention_tendency": b2.get("abstention_tendency"),
        "interpretations": [
            {
                "behavior": i.get("behavior"),
                "meaning": (i.get("meaning") or "")[:160],
                "confidence": i.get("confidence"),
                "memory_support": i.get("memory_support"),
            }
            for i in top
        ],
    }


def run_brain2_analyst(
    symbol: str,
    market: MarketStructureState,
    brain2: Brain2CognitionState,
    context: ContextState,
) -> Brain2AnalystReport:
    api_key = brain_stack.brain2_api_key()
    if not brain_stack.brain2_active():
        return Brain2AnalystReport(
            symbol=symbol,
            analyst_summary="Brain 2 inactive — set OPENAI_API_KEY for analyst layer.",
            environment_read="—",
            uncertainty_note="Use Brain-2 cognition output only.",
            intelligence_quality="DEGRADED",
            active=False,
            error="no_key_or_disabled",
        )

    payload = {
        "symbol": symbol,
        "context_event_risk": context.event_risk,
        "context_summary": (context.summary or "")[:400],
        "market_audit": market.to_dict(),
        "brain2_cognition": _compact_brain2(brain2),
    }

    system = (
        "You are AMRO Brain 2 Analyst. Analyze market structure and cognition state. "
        "Output JSON only. Use probabilistic language. "
        "FORBIDDEN: BUY, SELL, guaranteed profit, certainty claims, trade instructions. "
        "You do NOT approve execution — Brain 3 governance decides that."
    )
    user = (
        "Summarize the runtime payload for a trader dashboard in Thai-friendly short English "
        "(1-2 sentences each field). JSON keys: "
        "analyst_summary, environment_read, uncertainty_note, intelligence_quality "
        "(FULL|PARTIAL|DEGRADED).\n\n"
        f"PAYLOAD:\n{json.dumps(payload, default=str)[:12000]}"
    )

    try:
        client = OpenAI(api_key=api_key)
        resp = client.chat.completions.create(
            model=brain_stack.BRAIN2_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
            max_tokens=500,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        if any(w in raw.lower() for w in BANNED):
            logger.warning("[Brain 2 Analyst] banned language in output")
        data = json.loads(raw)
        report = Brain2AnalystReport(
            symbol=symbol,
            analyst_summary=str(data.get("analyst_summary", ""))[:600],
            environment_read=str(data.get("environment_read", ""))[:400],
            uncertainty_note=str(data.get("uncertainty_note", ""))[:400],
            intelligence_quality=str(data.get("intelligence_quality", "PARTIAL")),
            active=True,
        )
        logger.info(f"[Brain 2 Analyst] {symbol} quality={report.intelligence_quality}")
        return report
    except Exception as e:
        logger.error(f"[Brain 2 Analyst] {symbol}: {e}")
        return Brain2AnalystReport(
            symbol=symbol,
            analyst_summary="Brain 2 analyst unavailable.",
            environment_read="—",
            uncertainty_note=str(e)[:200],
            intelligence_quality="DEGRADED",
            active=False,
            error=str(e),
        )
