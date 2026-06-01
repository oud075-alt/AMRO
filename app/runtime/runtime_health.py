"""Runtime health evaluation — fail-closed states."""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any

import pandas as pd
from loguru import logger

from app.runtime.state_sync import check_mt5_sync


class RuntimeStateLevel(str, Enum):
    OK = "RUNTIME_OK"
    DEGRADED = "RUNTIME_DEGRADED"
    UNTRUSTED = "RUNTIME_UNTRUSTED"
    DISABLED = "RUNTIME_DISABLED"


@dataclass
class RuntimeHealth:
    level: RuntimeStateLevel
    reasons: list[str]
    data_stale: bool = False
    mt5_desync: bool = False
    missing_candles: bool = False
    invalid_spread: bool = False
    replay_mismatch: bool = False
    telemetry_corrupt: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_runtime_health(
    df: pd.DataFrame,
    symbol: str,
    max_stale_minutes: int = 180,
    context_error: bool = False,
    replay_mismatch: bool = False,
    execution_latency_breach: bool = False,
    telemetry_corrupt: bool = False,
) -> RuntimeHealth:
    reasons: list[str] = []
    level = RuntimeStateLevel.OK
    data_stale = False
    mt5_desync = False
    missing_candles = False
    invalid_spread = False

    if df.empty or len(df) < 50:
        return RuntimeHealth(RuntimeStateLevel.DISABLED, ["missing_candles"], missing_candles=True)

    try:
        last_ts = pd.Timestamp(df.index[-1])
        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize("UTC")
        age = datetime.now(timezone.utc) - last_ts.to_pydatetime().replace(tzinfo=timezone.utc)
        if age > timedelta(minutes=max_stale_minutes):
            data_stale = True
            reasons.append(f"stale_candles_age_min={int(age.total_seconds() // 60)}")
    except Exception:
        data_stale = True
        reasons.append("stale_timestamp_parse_failed")

    rng = (df["high"] - df["low"]) / df["close"]
    if rng.iloc[-1] > rng.tail(50).median() * 4:
        invalid_spread = True
        reasons.append("invalid_spread_conditions")
        level = RuntimeStateLevel.DEGRADED

    if context_error:
        reasons.append("api_inconsistency")
        level = RuntimeStateLevel.UNTRUSTED
    if replay_mismatch:
        reasons.append("replay_mismatch")
        level = RuntimeStateLevel.UNTRUSTED
    if execution_latency_breach:
        reasons.append("execution_latency_breach")
        level = RuntimeStateLevel.DEGRADED
    if telemetry_corrupt:
        reasons.append("telemetry_corruption")
        level = RuntimeStateLevel.UNTRUSTED

    mt5_ok, mt5_reason = check_mt5_sync(symbol)
    if not mt5_ok:
        mt5_desync = True
        reasons.append(mt5_reason)

    if data_stale:
        level = RuntimeStateLevel.UNTRUSTED
    if mt5_desync and level == RuntimeStateLevel.OK:
        level = RuntimeStateLevel.DEGRADED
    if len(reasons) >= 3:
        level = RuntimeStateLevel.DISABLED

    logger.info(f"[RuntimeHealth] {symbol} {level.value} {reasons}")
    return RuntimeHealth(
        level=level,
        reasons=reasons,
        data_stale=data_stale,
        mt5_desync=mt5_desync,
        missing_candles=missing_candles,
        invalid_spread=invalid_spread,
        replay_mismatch=replay_mismatch,
        telemetry_corrupt=telemetry_corrupt,
    )
