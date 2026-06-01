"""
AMRO — Candles API
GET /api/candles/{symbol}  — ส่ง OHLCV data สำหรับ Candlestick Chart
"""
from fastapi import APIRouter, Query
from loguru import logger
from app.intelligence.market_data import fetch_market_data

router = APIRouter(prefix="/api/candles", tags=["candles"])


@router.get("/{symbol:path}")
async def get_candles(
    symbol: str,
    interval: str = Query("1h", description="1m|5m|15m|1h|4h|1d"),
    limit: int = Query(100, description="จำนวน candle สูงสุด 500"),
):
    limit = min(limit, 500)

    # คำนวณ days ตาม interval เพื่อให้ได้ candle ครบ
    interval_days = {
        "1m":  max(3,   limit // 1440 + 2),
        "5m":  max(5,   limit // 288  + 2),
        "15m": max(7,   limit // 96   + 2),
        "1h":  max(10,  limit // 24   + 3),
        "4h":  max(30,  limit // 6    + 5),
        "1d":  max(200, limit + 10),
    }
    days = interval_days.get(interval, max(30, limit + 10))

    df = fetch_market_data(symbol=symbol, interval=interval, days=days)
    if df.empty:
        return {"candles": [], "symbol": symbol}

    df = df.tail(limit).copy()

    candles = []
    for ts, row in df.iterrows():
        try:
            if interval == "1d":
                # Daily bars: ส่งเป็น date string เพื่อหลีกเลี่ยง timezone offset ใน chart
                t = ts.strftime("%Y-%m-%d") if hasattr(ts, "strftime") else str(ts)[:10]
            else:
                # Intraday: ใช้ Unix timestamp (seconds)
                t = int(ts.timestamp())

            candles.append({
                "time":  t,
                "open":  round(float(row["open"]),  8),
                "high":  round(float(row["high"]),  8),
                "low":   round(float(row["low"]),   8),
                "close": round(float(row["close"]), 8),
            })
        except Exception:
            continue

    logger.info(f"Candles [{symbol}] {interval}: {len(candles)} bars")
    return {"candles": candles, "symbol": symbol, "interval": interval}
