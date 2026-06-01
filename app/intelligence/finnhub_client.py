"""
AMRO — Finnhub Client
Role: ดึงข่าวจริง + Economic Calendar สำหรับ Brain 1
"""
import time
import httpx
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Optional
from loguru import logger

from app.core.config import settings

FINNHUB_BASE = "https://finnhub.io/api/v1"

# แปลง AMRO symbol → Finnhub symbol
SYMBOL_MAP = {
    "GC=F":     "OANDA:XAU_USD",
    "EURUSD=X": "OANDA:EUR_USD",
    "GBPUSD=X": "OANDA:GBP_USD",
    "USDJPY=X": "OANDA:USD_JPY",
    "USDCHF=X": "OANDA:USD_CHF",
    "AUDUSD=X": "OANDA:AUD_USD",
    "USDCAD=X": "OANDA:USD_CAD",
    "NZDUSD=X": "OANDA:NZD_USD",
    "BTC/USDT": "BINANCE:BTCUSDT",
    "ETH/USDT": "BINANCE:ETHUSDT",
}

# keyword ค้นข่าวทั่วไปสำหรับแต่ละ symbol
NEWS_KEYWORDS = {
    "GC=F":     "gold OR XAUUSD OR XAU",
    "EURUSD=X": "EURUSD OR euro dollar",
    "GBPUSD=X": "GBPUSD OR sterling pound",
    "USDJPY=X": "USDJPY OR yen dollar",
    "BTC/USDT": "bitcoin OR BTC crypto",
    "ETH/USDT": "ethereum OR ETH crypto",
}


@dataclass
class FinnhubNews:
    headline: str
    summary: str
    source: str
    url: str
    datetime_str: str


@dataclass
class EconomicEvent:
    event: str
    country: str
    impact: str          # high / medium / low
    actual: Optional[str]
    estimate: Optional[str]
    prev: Optional[str]
    datetime_str: str


@dataclass
class FinnhubIntelligence:
    symbol: str
    news: list[FinnhubNews] = field(default_factory=list)
    economic_events: list[EconomicEvent] = field(default_factory=list)
    error: str = ""
    available: bool = True


def fetch_finnhub_intelligence(symbol: str) -> FinnhubIntelligence:
    """
    ดึงข่าว + economic calendar จาก Finnhub
    ถ้าไม่มี API key หรือ error → คืน empty intel (ไม่ crash)
    """
    api_key = settings.FINNHUB_API_KEY
    if not api_key:
        logger.warning("[Finnhub] FINNHUB_API_KEY ไม่ได้ตั้งค่า — ข้ามการดึงข่าว")
        return FinnhubIntelligence(symbol=symbol, available=False, error="No API key")

    intel = FinnhubIntelligence(symbol=symbol)
    headers = {"X-Finnhub-Token": api_key}

    # ── 1. Market News (general) ──────────────────────────────────
    try:
        resp = httpx.get(
            f"{FINNHUB_BASE}/news",
            params={"category": "general"},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        items = resp.json()[:10]  # เอา 10 ข่าวล่าสุด

        # กรองด้วย keyword ถ้ามี
        keyword_raw = NEWS_KEYWORDS.get(symbol, "").lower()
        keywords = [k.strip() for k in keyword_raw.split("OR")] if keyword_raw else []

        for item in items:
            headline = item.get("headline", "")
            summary  = item.get("summary", "")
            text     = (headline + " " + summary).lower()

            # ถ้ามี keyword → กรอง, ถ้าไม่มี → เอาทุกข่าว
            if keywords and not any(kw in text for kw in keywords):
                continue

            ts = item.get("datetime", 0)
            dt_str = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d %H:%M") if ts else "unknown"

            intel.news.append(FinnhubNews(
                headline=headline[:200],
                summary=summary[:300],
                source=item.get("source", ""),
                url=item.get("url", ""),
                datetime_str=dt_str,
            ))

        logger.info(f"[Finnhub] {symbol}: ดึงข่าวได้ {len(intel.news)} รายการ")

    except Exception as e:
        logger.warning(f"[Finnhub] News error: {e}")
        intel.error += f"news_error:{e}; "

    # ── 2. Economic Calendar (7 วันข้างหน้า + 2 วันที่ผ่านมา) ───
    try:
        today = datetime.utcnow()
        date_from = (today - timedelta(days=2)).strftime("%Y-%m-%d")
        date_to   = (today + timedelta(days=7)).strftime("%Y-%m-%d")

        resp = httpx.get(
            f"{FINNHUB_BASE}/calendar/economic",
            params={"from": date_from, "to": date_to},
            headers=headers,
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json()
        events_raw = data.get("economicCalendar", [])

        # กรองเฉพาะ high impact หรือ medium impact ของ USD (และ EUR ถ้าเป็น EURUSD)
        relevant_countries = _get_relevant_countries(symbol)

        for ev in events_raw:
            country = ev.get("country", "").upper()
            impact  = ev.get("impact", "").lower()

            if country not in relevant_countries:
                continue
            if impact not in ("high", "medium"):
                continue

            ts = ev.get("time", "")
            intel.economic_events.append(EconomicEvent(
                event=ev.get("event", ""),
                country=country,
                impact=impact,
                actual=str(ev.get("actual", "")) or None,
                estimate=str(ev.get("estimate", "")) or None,
                prev=str(ev.get("prev", "")) or None,
                datetime_str=ts,
            ))

        logger.info(f"[Finnhub] {symbol}: economic events {len(intel.economic_events)} รายการ")

    except Exception as e:
        logger.warning(f"[Finnhub] Calendar error: {e}")
        intel.error += f"calendar_error:{e}; "

    return intel


def format_for_brain1(intel: FinnhubIntelligence) -> str:
    """
    แปลง FinnhubIntelligence → text block สำหรับใส่ใน Brain 1 prompt
    """
    if not intel.available:
        return "Real-time news unavailable. Rely on technical analysis only."

    lines = []

    # ── News ──────────────────────────────────────────────────────
    if intel.news:
        lines.append("=== REAL-TIME NEWS (last 24h) ===")
        for i, n in enumerate(intel.news[:5], 1):
            lines.append(f"[{i}] [{n.datetime_str}] {n.source}: {n.headline}")
            if n.summary:
                lines.append(f"    {n.summary[:200]}")
        lines.append("")
    else:
        lines.append("=== NEWS: No relevant news found in last 24h ===\n")

    # ── Economic Calendar ─────────────────────────────────────────
    if intel.economic_events:
        lines.append("=== UPCOMING ECONOMIC EVENTS (next 7 days, high/medium impact) ===")
        for ev in intel.economic_events[:8]:
            actual_str = f" | Actual: {ev.actual}" if ev.actual else ""
            est_str    = f" | Est: {ev.estimate}" if ev.estimate else ""
            prev_str   = f" | Prev: {ev.prev}" if ev.prev else ""
            lines.append(
                f"[{ev.impact.upper()}] [{ev.datetime_str}] {ev.country}: {ev.event}"
                f"{actual_str}{est_str}{prev_str}"
            )
        lines.append("")
    else:
        lines.append("=== ECONOMIC CALENDAR: No high/medium impact events found ===\n")

    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────

def _get_relevant_countries(symbol: str) -> set:
    """กำหนดประเทศที่เกี่ยวข้องกับ symbol"""
    base = {"US"}   # USD เกี่ยวกับทุก symbol

    extra = {
        "EURUSD=X": {"EU", "DE", "FR"},
        "GBPUSD=X": {"GB", "UK"},
        "USDJPY=X": {"JP"},
        "USDCHF=X": {"CH"},
        "AUDUSD=X": {"AU"},
        "USDCAD=X": {"CA"},
        "NZDUSD=X": {"NZ"},
        "GC=F":     {"US"},   # Gold ขึ้นกับ USD เป็นหลัก
    }
    return base | extra.get(symbol, set())
