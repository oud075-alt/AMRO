"""
AMRO — Market Data Fetcher
รองรับ: Yahoo Finance (stocks/forex) + Binance (crypto)
MT5 จะเพิ่มทีหลัง
"""
import yfinance as yf
import ccxt
import pandas as pd
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger
from app.core.config import settings


# ─── Yahoo Finance (Stocks / Forex / Indices) ───────────────────────────────

def fetch_yahoo(
    symbol: str,
    interval: str = "1h",
    days: int = 30
) -> pd.DataFrame:
    """
    ดึงข้อมูลราคาจาก Yahoo Finance

    Args:
        symbol: เช่น "AAPL", "BTC-USD", "EURUSD=X", "^SET.BK"
        interval: 1m, 5m, 15m, 30m, 1h, 1d
        days: ย้อนหลังกี่วัน

    Returns:
        DataFrame columns: open, high, low, close, volume
    """
    try:
        end = datetime.now()
        start = end - timedelta(days=days)

        # yfinance 1.3+ ใช้ download() แทน Ticker.history() สำหรับ forex
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval=interval,
            progress=False,
            auto_adjust=True,
        )

        if df.empty:
            # fallback: ลอง Ticker.history()
            ticker = yf.Ticker(symbol)
            df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)

        if df.empty:
            logger.warning(f"No data for {symbol}")
            return pd.DataFrame()

        # Normalize columns (yfinance 1.3 ใช้ MultiIndex columns)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]

        # เลือก columns ที่มีอยู่
        available = [c for c in ["open", "high", "low", "close", "volume"] if c in df.columns]
        df = df[available].copy()
        if "volume" not in df.columns:
            df["volume"] = 0
        df = df[["open", "high", "low", "close", "volume"]]
        df.index.name = "timestamp"
        df.dropna(inplace=True)

        logger.info(f"Fetched {len(df)} rows for {symbol} ({interval})")
        return df

    except Exception as e:
        logger.error(f"Yahoo fetch error for {symbol}: {e}")
        return pd.DataFrame()


# ─── Binance (Crypto) ────────────────────────────────────────────────────────

_binance_client: Optional[ccxt.binance] = None

def get_binance() -> ccxt.binance:
    global _binance_client
    if _binance_client is None:
        _binance_client = ccxt.binance({
            "apiKey": settings.BINANCE_API_KEY or None,
            "secret": settings.BINANCE_SECRET_KEY or None,
            "enableRateLimit": True,
        })
    return _binance_client


def fetch_binance(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int = 200
) -> pd.DataFrame:
    """
    ดึงข้อมูลจาก Binance

    Args:
        symbol: เช่น "BTC/USDT", "ETH/USDT"
        timeframe: 1m, 5m, 15m, 1h, 4h, 1d
        limit: จำนวน candle

    Returns:
        DataFrame columns: open, high, low, close, volume
    """
    try:
        exchange = get_binance()
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df.set_index("timestamp", inplace=True)
        df.dropna(inplace=True)

        logger.info(f"Fetched {len(df)} candles for {symbol} ({timeframe}) from Binance")
        return df

    except Exception as e:
        logger.error(f"Binance fetch error for {symbol}: {e}")
        return pd.DataFrame()


def _timeframe_ms(timeframe: str) -> int:
    units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
    if len(timeframe) < 2:
        return 3_600_000
    n = int(timeframe[:-1])
    return n * units.get(timeframe[-1], 3_600_000)


def fetch_binance_range(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    since_ms: int | None = None,
    until_ms: int | None = None,
    max_candles: int = 1500,
) -> pd.DataFrame:
    """Fetch Binance OHLCV between since/until (UTC ms), paginated."""
    try:
        exchange = get_binance()
        tf_ms = _timeframe_ms(timeframe)
        since = since_ms
        rows: list[list[float]] = []
        while len(rows) < max_candles:
            batch = exchange.fetch_ohlcv(
                symbol, timeframe=timeframe, since=since, limit=min(1000, max_candles - len(rows))
            )
            if not batch:
                break
            for row in batch:
                ts = int(row[0])
                if until_ms is not None and ts > until_ms:
                    break
                rows.append(row)
            last_ts = int(batch[-1][0])
            if until_ms is not None and last_ts >= until_ms:
                break
            if len(batch) < 1000:
                break
            since = last_ts + tf_ms
            if until_ms is not None and since > until_ms:
                break

        if not rows:
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        if until_ms is not None:
            until_ts = pd.Timestamp(until_ms, unit="ms", tz="UTC")
            df = df[df["timestamp"] <= until_ts]
        df.set_index("timestamp", inplace=True)
        df = df[~df.index.duplicated(keep="last")]
        df.dropna(inplace=True)
        logger.info(f"Fetched {len(df)} historical candles for {symbol} ({timeframe})")
        return df
    except Exception as e:
        logger.error(f"Binance range fetch error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_historical_as_of(
    symbol: str,
    as_of: str | datetime,
    *,
    interval: str = "1h",
    lookback_days: int = 45,
    source: str = "auto",
) -> pd.DataFrame:
    """
    OHLCV ending at as_of (inclusive) — for Brain-2 historical training probes.
    as_of: ISO date/datetime e.g. '2020-03-12' or '2020-03-12T12:00:00'
    """
    if isinstance(as_of, str):
        end = pd.Timestamp(as_of, tz="UTC")
    else:
        end = pd.Timestamp(as_of).tz_convert("UTC") if pd.Timestamp(as_of).tzinfo else pd.Timestamp(as_of, tz="UTC")
    start = end - timedelta(days=lookback_days)
    until_ms = int(end.timestamp() * 1000)
    since_ms = int(start.timestamp() * 1000)

    if source == "binance" or (source == "auto" and "/" in symbol):
        return fetch_binance_range(symbol, timeframe=interval, since_ms=since_ms, until_ms=until_ms)

    try:
        df = yf.download(
            symbol,
            start=start.to_pydatetime().replace(tzinfo=None),
            end=(end + timedelta(hours=1)).to_pydatetime().replace(tzinfo=None),
            interval=interval,
            progress=False,
            auto_adjust=True,
        )
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        if "volume" not in df.columns:
            df["volume"] = 0
        df = df[["open", "high", "low", "close", "volume"]].copy()
        df.index = pd.to_datetime(df.index, utc=True)
        df = df[df.index <= end]
        df.dropna(inplace=True)
        return df
    except Exception as e:
        logger.error(f"Yahoo historical fetch error for {symbol}: {e}")
        return pd.DataFrame()


# ─── Unified Fetcher ─────────────────────────────────────────────────────────

def fetch_market_data(
    symbol: str,
    source: str = "auto",
    interval: str = "1h",
    days: int = 30
) -> pd.DataFrame:
    """
    Unified function — เลือก source อัตโนมัติ หรือระบุเอง

    source: "auto" | "yahoo" | "binance"
    """
    if source == "binance" or (source == "auto" and "/" in symbol):
        return fetch_binance(symbol, timeframe=interval, limit=days * 24)
    else:
        return fetch_yahoo(symbol, interval=interval, days=days)
