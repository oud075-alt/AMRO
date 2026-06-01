"""
AMRO v2.0 — Brain 1: Constitutional Market Intelligence Collector

Identity:
    A disciplined probabilistic observer tasked with gathering and transmitting
    market reality without distorting uncertainty.

Role:
    SENSOR — not Judge, not Analyst, not Signal Generator.

Constitutional Rules:
    - Observe reality honestly
    - Communicate uncertainty faithfully
    - Never close the case
    - Pass raw intelligence to Brain 2 without narrative distortion

Note: Powered by GPT-4o-mini (switched from Gemini)
"""
import json
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger
from openai import OpenAI

from app.intelligence import brain_stack


# ── AMRO Language Constitution ─────────────────────────────────────────────────
BANNED_LANGUAGE = [
    "confirmed", "guaranteed", "strong setup", "perfect structure",
    "definitely", "certainly", "will go up", "will go down",
    "strong bullish momentum confirmed", "clear signal",
]

# ── Output Dataclass ───────────────────────────────────────────────────────────

@dataclass
class IntelligenceReport:
    """
    รายงานจาก Brain 1 — เป็น observational เท่านั้น
    ไม่มี final conclusion ไม่มี direction call
    """
    symbol: str

    observations: list[str] = field(default_factory=list)
    market_context: list[str] = field(default_factory=list)

    news_relevance_level: str = "INCONCLUSIVE"
    news_relevance_desc: str = ""
    reaction_persistence: str = "UNCERTAIN"

    uncertainties: list[str] = field(default_factory=list)

    sentiment_direction: str = "INCONCLUSIVE"
    sentiment_score: float = 0.0
    risk_level: str = "MEDIUM"
    key_events: list[str] = field(default_factory=list)

    raw_response: str = ""
    intelligence_quality: str = "PARTIAL"


# ── System Prompt Constitution ─────────────────────────────────────────────────

BRAIN1_SYSTEM_PROMPT = """You are Brain 1 of AMRO — a multi-AI trading intelligence system.

YOUR IDENTITY:
    Constitutional Market Intelligence Collector
    A disciplined probabilistic observer tasked with gathering and transmitting
    market reality without distorting uncertainty.

YOUR ROLE:
    SENSOR — not Judge, not Analyst, not Signal Generator.
    You observe and transmit. Brain 2 will analyze. Brain 3 will judge.

YOUR MISSION:
    Gather market observations for: {asset_name} ({symbol})

CORRECT MINDSET:
    "I must observe reality honestly and communicate uncertainty faithfully."

WRONG MINDSET (strictly forbidden):
    "I must predict the market."
    "I must give a clear direction."
    "I must complete the narrative."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ALLOWED COGNITION:
    ✓ pattern observation
    ✓ contextual association
    ✓ probabilistic description
    ✓ contradiction reporting
    ✓ uncertainty exposure
    ✓ multi-factor summarization

FORBIDDEN COGNITION:
    ✗ certainty claims
    ✗ execution decisions
    ✗ guaranteed direction
    ✗ narrative completion
    ✗ hidden assumptions
    ✗ sensationalism
    ✗ narrative inflation

BANNED LANGUAGE (never use these words/phrases):
    "confirmed" / "guaranteed" / "strong setup" / "perfect structure"
    "definitely" / "certainly" / "will go up" / "will go down"
    "clear signal" / "strong bullish momentum confirmed"
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LANGUAGE CONSTITUTION — News Reporting:

BAD (forbidden):
    "Fed news is bullish for USDJPY."

GOOD (required):
    "Recent Fed commentary may increase probability of USD strength persistence,
    though market reaction consistency remains mixed."

If news is conflicting, weak, unclear, or already priced-in, you MUST say so:
    "Macro relevance currently inconclusive. Market response lacks directional consistency."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CRITICAL RULE:
    Do NOT provide a final conclusion.
    Do NOT close the case.
    Your output is raw intelligence — Brain 2 will interpret it.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Respond ONLY in this exact JSON (no markdown, no extra text):
{{
  "observations": [
    "volatility behavior description",
    "session liquidity observation",
    "price structure observation",
    "cross-asset behavior"
  ],
  "market_context": [
    "risk sentiment description (risk-on / risk-off / mixed)",
    "macro focus description",
    "directional persistence assessment"
  ],
  "news_relevance_level": "LOW" or "MEDIUM" or "HIGH" or "INCONCLUSIVE",
  "news_relevance_desc": "probabilistic description of news impact — no certainty claims",
  "reaction_persistence": "LIKELY" or "UNLIKELY" or "UNCERTAIN",
  "uncertainties": [
    "what is conflicting or unclear",
    "what is not confirmed",
    "what needs further observation"
  ],
  "sentiment_direction": "CAUTIOUS_BULLISH" or "CAUTIOUS_BEARISH" or "INCONCLUSIVE" or "MIXED",
  "sentiment_score": number -1.0 to 1.0,
  "risk_level": "LOW" or "MEDIUM" or "HIGH",
  "key_events": ["event descriptions — factual, no interpretation"],
  "intelligence_quality": "FULL" or "PARTIAL" or "DEGRADED"
}}"""


# ── Main Function ──────────────────────────────────────────────────────────────

def run_gemini_intelligence(symbol: str, real_news_text: str = "") -> IntelligenceReport:
    """
    Brain 1: GPT-4o-mini ทำหน้าที่ Sensor เท่านั้น
    สังเกต — รวบรวม — ส่งต่อ — ไม่ตัดสิน
    real_news_text: ข่าวจริงจาก Finnhub (ถ้ามี)
    """
    api_key = brain_stack.brain1_api_key()
    if not brain_stack.brain1_active():
        logger.warning("[Brain 1] No OPENAI_API_KEY_INTEL — degraded fallback")
        return _degraded_report(symbol, "No OPENAI_API_KEY_INTEL")

    try:
        client  = OpenAI(api_key=api_key)
        asset_name = _symbol_to_name(symbol)

        system_prompt = BRAIN1_SYSTEM_PROMPT.format(
            asset_name=asset_name,
            symbol=symbol,
        )

        # ใส่ข่าวจริงถ้ามี
        if real_news_text and real_news_text.strip():
            news_block = (
                f"\n\n--- REAL-TIME MARKET DATA PROVIDED ---\n"
                f"{real_news_text}\n"
                f"--- END OF REAL-TIME DATA ---\n\n"
                f"Use the above real data as your primary source. "
                f"Apply your constitutional rules when interpreting it."
            )
        else:
            news_block = " No real-time data available — rely on general knowledge with high uncertainty."

        user_prompt = (
            f"Observe and report market intelligence for {asset_name} ({symbol}) now."
            f"{news_block}\n"
            f"Follow your constitutional rules strictly. "
            f"Do NOT conclude. Do NOT predict. Only observe and transmit."
        )

        response = client.chat.completions.create(
            model=brain_stack.BRAIN1_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.25,
            max_tokens=700,
            response_format={"type": "json_object"},
        )

        raw  = response.choices[0].message.content.strip()
        data = json.loads(raw)

        # ตรวจ banned language
        raw_lower = raw.lower()
        violations = [w for w in BANNED_LANGUAGE if w.lower() in raw_lower]
        if violations:
            logger.warning(f"[Brain 1] Language violation detected: {violations}")

        report = IntelligenceReport(
            symbol=symbol,
            observations=data.get("observations", []),
            market_context=data.get("market_context", []),
            news_relevance_level=data.get("news_relevance_level", "INCONCLUSIVE"),
            news_relevance_desc=data.get("news_relevance_desc", ""),
            reaction_persistence=data.get("reaction_persistence", "UNCERTAIN"),
            uncertainties=data.get("uncertainties", []),
            sentiment_direction=data.get("sentiment_direction", "INCONCLUSIVE"),
            sentiment_score=float(data.get("sentiment_score", 0.0)),
            risk_level=data.get("risk_level", "MEDIUM"),
            key_events=data.get("key_events", []),
            intelligence_quality=data.get("intelligence_quality", "PARTIAL"),
            raw_response=raw,
        )

        logger.info(
            f"[Brain 1 — GPT] {symbol}: "
            f"direction={report.sentiment_direction} "
            f"score={report.sentiment_score:+.2f} "
            f"risk={report.risk_level} "
            f"news={report.news_relevance_level} "
            f"quality={report.intelligence_quality}"
        )
        logger.info(f"[Brain 1] Observations: {len(report.observations)} | "
                    f"Uncertainties: {len(report.uncertainties)}")

        return report

    except json.JSONDecodeError as e:
        logger.error(f"[Brain 1] JSON parse error: {e}")
        return _degraded_report(symbol, f"JSON parse error: {e}")
    except Exception as e:
        logger.error(f"[Brain 1] Error: {e}")
        return _degraded_report(symbol, str(e))


# ── Helpers ────────────────────────────────────────────────────────────────────

def _symbol_to_name(symbol: str) -> str:
    names = {
        "EURUSD=X": "Euro / US Dollar",
        "GBPUSD=X": "British Pound / US Dollar",
        "USDJPY=X": "US Dollar / Japanese Yen",
        "USDCHF=X": "US Dollar / Swiss Franc",
        "AUDUSD=X": "Australian Dollar / US Dollar",
        "USDCAD=X": "US Dollar / Canadian Dollar",
        "NZDUSD=X": "New Zealand Dollar / US Dollar",
        "GC=F":     "Gold (XAU/USD)",
        "BTC/USDT": "Bitcoin / US Dollar",
        "ETH/USDT": "Ethereum / US Dollar",
    }
    return names.get(symbol, symbol)


def _degraded_report(symbol: str, reason: str) -> IntelligenceReport:
    """Fallback เมื่อ GPT ไม่พร้อม — ส่ง degraded report แทน error"""
    return IntelligenceReport(
        symbol=symbol,
        observations=[f"Intelligence collection unavailable: {reason}"],
        market_context=["Context data unavailable — proceeding with technical analysis only"],
        news_relevance_level="INCONCLUSIVE",
        news_relevance_desc="News intelligence unavailable. Brain 2 should rely on technical data only.",
        reaction_persistence="UNCERTAIN",
        uncertainties=[
            "Full macro context not available",
            "News sentiment not verified",
            "Cross-asset behavior not assessed",
        ],
        sentiment_direction="INCONCLUSIVE",
        sentiment_score=0.0,
        risk_level="MEDIUM",
        key_events=[],
        intelligence_quality="DEGRADED",
        raw_response="",
    )
