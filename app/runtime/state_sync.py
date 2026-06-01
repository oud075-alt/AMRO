"""MT5 / external heartbeat sync check."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta


def check_mt5_sync(symbol: str) -> tuple[bool, str]:
    try:
        from app.api import ea_bridge as ea_bridge_module

        hb = ea_bridge_module._heartbeats
        key = symbol.replace("=X", "").replace("/", "")
        if not hb:
            return True, "mt5_not_configured"
        sym_hb = hb.get(key) or hb.get(symbol)
        if sym_hb is None:
            return False, "mt5_desync_no_heartbeat"
        recv = sym_hb.get("received_at", "")
        if recv:
            recv_dt = datetime.fromisoformat(recv.replace("Z", "+00:00"))
            if datetime.now(timezone.utc) - recv_dt.replace(tzinfo=timezone.utc) > timedelta(minutes=30):
                return False, "mt5_heartbeat_stale"
        return True, "mt5_ok"
    except Exception:
        return True, "mt5_check_skipped"
