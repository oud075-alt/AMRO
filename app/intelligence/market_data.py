"""
AMRO — Market Data Fetcher
รองรับ: Yahoo Finance (stocks/forex) + Binance (crypto)
MT5 จะเพิ่มทีหลัง
"""
import time
import yfinance as yf
import ccxt
import pandas as pd
import requests
from datetime import datetime, timedelta, timezone
from typing import Optional
from loguru import logger
from app.core.config import settings

_MARKET_DATA_CACHE: dict[tuple, tuple[float, pd.DataFrame]] = {}
_MARKET_DATA_CACHE_TTL_SEC = 45
_MARKET_DATA_STALE_SEC = 900


# ─── Yahoo Finance (Stocks / Forex / Indices) ───────────────────────────────

_YAHOO_SYMBOL_FALLBACKS: dict[str, list[str]] = {
    "GC=F": ["XAUUSD=X"],
    "XAUUSD": ["GC=F", "XAUUSD=X"],
    "NZDUSD=X": ["NZD=X"],
}

# When Yahoo is blocked on VPS/datacenter IPs, use liquid Binance proxies.
_BINANCE_PROXY_SYMBOLS: dict[str, str] = {
    "GC=F": "PAXG/USDT",
    "XAUUSD": "PAXG/USDT",
    "XAUUSD=X": "PAXG/USDT",
}

# Kraken spot FX — reliable from VPS when Yahoo rate-limits datacenter IPs.
_KRAKEN_FOREX: dict[str, str] = {
    "EURUSD=X": "EUR/USD",
    "GBPUSD=X": "GBP/USD",
    "USDJPY=X": "USD/JPY",
    "USDCHF=X": "USD/CHF",
    "AUDUSD=X": "AUD/USD",
    "USDCAD=X": "USD/CAD",
}

# Finnhub OANDA symbols (requires FINNHUB_API_KEY)
_FINNHUB_FOREX: dict[str, str] = {
    "GC=F": "OANDA:XAU_USD",
    "XAUUSD=X": "OANDA:XAU_USD",
    "EURUSD=X": "OANDA:EUR_USD",
    "GBPUSD=X": "OANDA:GBP_USD",
    "USDJPY=X": "OANDA:USD_JPY",
    "USDCHF=X": "OANDA:USD_CHF",
    "AUDUSD=X": "OANDA:AUD_USD",
    "USDCAD=X": "OANDA:USD_CAD",
    "NZDUSD=X": "OANDA:NZD_USD",
}

_FINNHUB_RESOLUTION: dict[str, int] = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "1d": "D",
}


def _candle_limit(interval: str, days: int) -> int:
    per_day = {"1m": 1440, "5m": 288, "15m": 96, "30m": 48, "1h": 24, "4h": 6, "1d": 1}
    return min(1500, max(200, days * per_day.get(interval, 24)))


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
_kraken_client: Optional[ccxt.kraken] = None


def get_kraken() -> ccxt.kraken:
    global _kraken_client
    if _kraken_client is None:
        _kraken_client = ccxt.kraken({"enableRateLimit": True})
    return _kraken_client


def fetch_kraken_forex(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 200,
) -> pd.DataFrame:
    pair = _KRAKEN_FOREX.get(symbol)
    if not pair:
        return pd.DataFrame()
    try:
        exchange = get_kraken()
        ohlcv = exchange.fetch_ohlcv(pair, timeframe=timeframe, limit=limit)
        if not ohlcv:
            return pd.DataFrame()
        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"],
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        df.dropna(inplace=True)
        logger.info(f"Fetched {len(df)} rows for {symbol} via Kraken {pair} ({timeframe})")
        return df
    except Exception as e:
        logger.error(f"Kraken fetch error for {symbol} ({pair}): {e}")
        return pd.DataFrame()


def get_binance() -> ccxt.binance:
    global _binance_client
    if _binance_client is None:
        _binance_client = ccxt.binance({
            "apiKey": settings.BINANCE_API_KEY or None,
            "secret": settings.BINANCE_SECRET_KEY or None,
            "enableRateLimit": True,
        })
    return _binance_client


def _parse_yahoo_chart_result(result: dict, symbol: str, interval: str, days: int) -> pd.DataFrame:
    quote_data = result["indicators"]["quote"][0]
    ts = result.get("timestamp") or []
    if not ts:
        return pd.DataFrame()
    df = pd.DataFrame(
        {
            "open": quote_data.get("open"),
            "high": quote_data.get("high"),
            "low": quote_data.get("low"),
            "close": quote_data.get("close"),
            "volume": quote_data.get("volume"),
        },
        index=pd.to_datetime(ts, unit="s", utc=True),
    )
    df.index.name = "timestamp"
    df["volume"] = df["volume"].fillna(0)
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    cutoff = pd.Timestamp.now(tz="UTC") - timedelta(days=days)
    df = df[df.index >= cutoff]
    if df.empty:
        return pd.DataFrame()
    logger.info(f"Fetched {len(df)} rows for {symbol} via Yahoo chart API ({interval})")
    return df


def _yahoo_chart_request(
    encoded_symbol: str,
    yahoo_interval: str,
    range_param: str,
    days: int,
    headers: dict,
) -> pd.DataFrame:
    from urllib.parse import quote

    sym = encoded_symbol if "%" in encoded_symbol else quote(encoded_symbol, safe="")
    now_sec = int(datetime.now(timezone.utc).timestamp())
    period1 = now_sec - days * 86400
    param_sets = [
        {"interval": yahoo_interval, "range": range_param},
        {"interval": yahoo_interval, "period1": period1, "period2": now_sec},
    ]
    for params in param_sets:
        for host in ("query1.finance.yahoo.com", "query2.finance.yahoo.com"):
            try:
                url = f"https://{host}/v8/finance/chart/{sym}"
                resp = requests.get(url, params=params, headers=headers, timeout=25)
                resp.raise_for_status()
                chart = resp.json().get("chart") or {}
                if chart.get("error"):
                    continue
                results = chart.get("result") or []
                if not results:
                    continue
                df = _parse_yahoo_chart_result(results[0], sym, yahoo_interval, days)
                if not df.empty:
                    return df
            except Exception:
                continue
    return pd.DataFrame()


def fetch_yahoo_chart(symbol: str, interval: str = "1h", days: int = 30) -> pd.DataFrame:
    """Yahoo v8 chart API — works when yfinance fails (e.g. VPS/datacenter)."""
    yahoo_interval = {
        "1m": "1m",
        "5m": "5m",
        "15m": "15m",
        "30m": "30m",
        "1h": "60m",
        "1d": "1d",
    }.get(interval)
    if not yahoo_interval:
        return pd.DataFrame()
    if days <= 7:
        range_param = "7d"
    elif days <= 30:
        range_param = "1mo"
    elif days <= 90:
        range_param = "3mo"
    else:
        range_param = "6mo"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    try:
        return _yahoo_chart_request(symbol, yahoo_interval, range_param, days, headers)
    except Exception as e:
        logger.error(f"Yahoo chart API error for {symbol}: {e}")
        return pd.DataFrame()


def fetch_yahoo_chart_retry(
    symbol: str,
    interval: str = "1h",
    days: int = 30,
    attempts: int = 4,
) -> pd.DataFrame:
    """Retry chart fetch — NZD/USD has no Kraken pair and is rate-limited more often on VPS."""
    for attempt in range(attempts):
        df = fetch_yahoo_chart(symbol, interval=interval, days=days)
        if not df.empty:
            return df
        if attempt < attempts - 1:
            time.sleep(1.25 * (attempt + 1))
    return pd.DataFrame()


def fetch_finnhub_candles(symbol: str, interval: str = "1h", days: int = 30) -> pd.DataFrame:
    """OHLCV from Finnhub forex candles (needs FINNHUB_API_KEY)."""
    api_key = settings.FINNHUB_API_KEY
    finnhub_sym = _FINNHUB_FOREX.get(symbol)
    resolution = _FINNHUB_RESOLUTION.get(interval)
    if not api_key or not finnhub_sym or resolution is None:
        return pd.DataFrame()
    try:
        end = int(datetime.now(timezone.utc).timestamp())
        start = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp())
        resp = requests.get(
            "https://finnhub.io/api/v1/forex/candle",
            params={
                "symbol": finnhub_sym,
                "resolution": resolution,
                "from": start,
                "to": end,
                "token": api_key,
            },
            timeout=25,
        )
        resp.raise_for_status()
        payload = resp.json()
        if payload.get("s") != "ok":
            logger.warning(f"Finnhub candles unavailable for {symbol}: {payload.get('s')}")
            return pd.DataFrame()
        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(payload["t"], unit="s", utc=True),
                "open": payload["o"],
                "high": payload["h"],
                "low": payload["l"],
                "close": payload["c"],
                "volume": payload.get("v", [0] * len(payload["t"])),
            }
        )
        df = df.set_index("timestamp")
        df.dropna(inplace=True)
        logger.info(f"Fetched {len(df)} rows for {symbol} via Finnhub ({interval})")
        return df
    except Exception as e:
        logger.error(f"Finnhub candle error for {symbol}: {e}")
        return pd.DataFrame()


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

def _fetch_yahoo_with_fallbacks(symbol: str, interval: str, days: int) -> pd.DataFrame:
    candidates = [symbol]
    for alt in _YAHOO_SYMBOL_FALLBACKS.get(symbol, []):
        if alt not in candidates:
            candidates.append(alt)

    limit = _candle_limit(interval, days)

    chart_attempts = 5 if symbol == "NZDUSD=X" else 3

    def _try_chart_api() -> pd.DataFrame:
        for candidate in candidates:
            df = fetch_yahoo_chart_retry(
                candidate, interval=interval, days=days, attempts=chart_attempts
            )
            if not df.empty:
                if candidate != symbol:
                    logger.info(f"Yahoo chart fallback {symbol} -> {candidate} ({len(df)} rows)")
                else:
                    logger.info(f"Market data {symbol} via Yahoo chart API")
                return df
        return pd.DataFrame()

    def _try_kraken() -> pd.DataFrame:
        if symbol not in _KRAKEN_FOREX:
            return pd.DataFrame()
        logger.warning(f"Yahoo unavailable for {symbol}; using Kraken {_KRAKEN_FOREX[symbol]}")
        return fetch_kraken_forex(symbol, timeframe=interval, limit=limit)

    def _try_binance_proxy() -> pd.DataFrame:
        proxy = _BINANCE_PROXY_SYMBOLS.get(symbol)
        if not proxy:
            return pd.DataFrame()
        logger.warning(f"Yahoo unavailable for {symbol}; using Binance proxy {proxy}")
        return fetch_binance(proxy, timeframe=interval, limit=limit)

    # On VPS/datacenter IPs yfinance often returns empty JSON (see YFTzMissingError in logs).
    if settings.APP_ENV == "production":
        df = _try_chart_api()
        if not df.empty:
            return df
        df = _try_kraken()
        if not df.empty:
            return df
        df = _try_binance_proxy()
        if not df.empty:
            return df
        df = fetch_finnhub_candles(symbol, interval=interval, days=days)
        if not df.empty:
            return df
        return pd.DataFrame()

    for candidate in candidates:
        df = fetch_yahoo(candidate, interval=interval, days=days)
        if not df.empty:
            if candidate != symbol:
                logger.info(f"Yahoo fallback symbol {symbol} -> {candidate} ({len(df)} rows)")
            return df

    df = _try_chart_api()
    if not df.empty:
        return df

    df = _try_kraken()
    if not df.empty:
        return df

    df = fetch_finnhub_candles(symbol, interval=interval, days=days)
    if not df.empty:
        return df

    return _try_binance_proxy()


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
    cache_key = (symbol, interval, days, source)
    now = time.time()
    ttl = 120 if symbol == "NZDUSD=X" else _MARKET_DATA_CACHE_TTL_SEC
    stale_ttl = 1800 if symbol == "NZDUSD=X" else _MARKET_DATA_STALE_SEC
    cached = _MARKET_DATA_CACHE.get(cache_key)
    if cached and (now - cached[0]) < ttl:
        return cached[1].copy()

    limit = _candle_limit(interval, days)
    if source == "binance" or (source == "auto" and "/" in symbol):
        df = fetch_binance(symbol, timeframe=interval, limit=limit)
    else:
        df = _fetch_yahoo_with_fallbacks(symbol, interval=interval, days=days)

    if df.empty and cached and (now - cached[0]) < stale_ttl:
        logger.warning(f"Serving stale market data for {symbol} (age={int(now - cached[0])}s)")
        return cached[1].copy()

    if not df.empty:
        _MARKET_DATA_CACHE[cache_key] = (now, df.copy())
    return df
