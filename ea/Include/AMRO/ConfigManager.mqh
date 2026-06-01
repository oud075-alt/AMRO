//+------------------------------------------------------------------+
//| AMRO — ConfigManager.mqh                                         |
//| Role: Centralize all external inputs and runtime toggles         |
//| Constitutional Rule: configuration is observable and auditable   |
//+------------------------------------------------------------------+
#ifndef AMRO_CONFIG_MANAGER_MQH
#define AMRO_CONFIG_MANAGER_MQH

//+------------------------------------------------------------------+
//| AMRO EA Configuration Container                                  |
//| All inputs flow through here — single source of truth            |
//+------------------------------------------------------------------+
struct AMROConfig
{
    // ── API Connection ─────────────────────────────────────────────
    string   api_base_url;           // e.g. http://localhost:8000
    string   api_key;                // Bearer token for AMRO server
    int      request_timeout_ms;     // HTTP timeout per request
    int      max_retries;            // retry count on transient failure

    // ── Polling Intervals ─────────────────────────────────────────
    int      decision_poll_ms;       // how often to poll /ea/decision
    int      heartbeat_interval_ms;  // how often to send heartbeat
    int      telemetry_interval_ms;  // how often to send telemetry

    // ── Risk Guards ───────────────────────────────────────────────
    double   max_spread_points;      // reject execution above this spread
    double   max_slippage_points;    // max allowed slippage
    int      stale_signal_seconds;   // reject decision older than N seconds
    bool     emergency_close_all;    // runtime kill switch

    // ── Execution Behaviour ───────────────────────────────────────
    double   base_lot;               // base lot before lot_scale applied
    bool     dry_run;                // if true: log only, no real orders
    string   symbol_whitelist;       // comma-separated allowed symbols
    int      magic_number;           // EA magic number for order tracking

    // ── Logging ───────────────────────────────────────────────────
    bool     verbose_log;            // extra log output for debugging
};

//+------------------------------------------------------------------+
//| Validate config — returns empty string if OK, else error message |
//+------------------------------------------------------------------+
string ConfigValidate(const AMROConfig &cfg)
{
    if (StringLen(cfg.api_base_url) < 7)
        return "api_base_url is empty or too short";
    if (cfg.request_timeout_ms < 1000)
        return "request_timeout_ms must be >= 1000";
    if (cfg.decision_poll_ms < 500)
        return "decision_poll_ms must be >= 500";
    if (cfg.heartbeat_interval_ms < 1000)
        return "heartbeat_interval_ms must be >= 1000";
    if (cfg.max_spread_points < 0)
        return "max_spread_points cannot be negative";
    if (cfg.base_lot <= 0)
        return "base_lot must be > 0";
    if (cfg.magic_number <= 0)
        return "magic_number must be > 0";
    return "";
}

//+------------------------------------------------------------------+
//| Check if a symbol is whitelisted                                  |
//| Empty whitelist = allow all                                       |
//+------------------------------------------------------------------+
bool ConfigSymbolAllowed(const AMROConfig &cfg, const string symbol)
{
    if (StringLen(cfg.symbol_whitelist) == 0) return true;

    string list = cfg.symbol_whitelist;
    string token = "";
    int i = 0;
    int len = StringLen(list);

    while (i <= len)
    {
        ushort c = (i < len) ? StringGetCharacter(list, i) : ',';
        if (c == ',' || c == ';')
        {
            StringTrimLeft(token);
            StringTrimRight(token);
            if (token == symbol) return true;
            token = "";
        }
        else
        {
            token += ShortToString(c);
        }
        i++;
    }
    return false;
}

//+------------------------------------------------------------------+
//| Log config summary to journal (called once on EA init)           |
//+------------------------------------------------------------------+
void ConfigPrint(const AMROConfig &cfg)
{
    PrintFormat("[AMRO Config] url=%s timeout=%dms poll=%dms hb=%dms "
                "spread=%.1f lot=%.2f dry_run=%s magic=%d",
                cfg.api_base_url,
                cfg.request_timeout_ms,
                cfg.decision_poll_ms,
                cfg.heartbeat_interval_ms,
                cfg.max_spread_points,
                cfg.base_lot,
                cfg.dry_run ? "YES" : "NO",
                cfg.magic_number);
}

#endif // AMRO_CONFIG_MANAGER_MQH
