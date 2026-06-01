//+------------------------------------------------------------------+
//| AMRO — TelemetryLogger.mqh                                       |
//| Role: structured log + async telemetry transmission             |
//| Constitutional Rule: log reality as-is — no filtering, no spin  |
//+------------------------------------------------------------------+
#ifndef AMRO_TELEMETRY_LOGGER_MQH
#define AMRO_TELEMETRY_LOGGER_MQH

#include "ConfigManager.mqh"
#include "ApiClient.mqh"
#include "JsonParser.mqh"

//── Log levels ────────────────────────────────────────────────────
#define TLOG_INFO    "INFO"
#define TLOG_WARN    "WARN"
#define TLOG_ERROR   "ERROR"
#define TLOG_EXEC    "EXEC"
#define TLOG_GUARD   "GUARD"
#define TLOG_HEART   "HEARTBEAT"

//+------------------------------------------------------------------+
//| TelemetryLogger state                                            |
//+------------------------------------------------------------------+
class CTelemetryLogger
{
private:
    AMROConfig  m_cfg;
    datetime    m_last_telemetry;
    bool        m_enabled;

public:
    CTelemetryLogger() : m_last_telemetry(0), m_enabled(true) {}

    void Init(const AMROConfig &cfg)
    {
        m_cfg     = cfg;
        m_enabled = true;
        _LocalLog(TLOG_INFO, _Symbol, "TelemetryLogger initialised", 0, 0);
    }

    void Disable() { m_enabled = false; }

    //── Local journal log (always fires) ──────────────────────────
    void Log(const string level,
             const string symbol,
             const string message,
             const double price  = 0.0,
             const long   ticket = 0)
    {
        _LocalLog(level, symbol, message, price, ticket);
    }

    //── Send telemetry to server (rate-limited by telemetry_interval)
    void SendTelemetry(const string symbol,
                       const string event_type,
                       const string detail,
                       const double price  = 0.0,
                       const long   ticket = 0)
    {
        if (!m_enabled) return;

        datetime now = TimeCurrent();
        if ((int)(now - m_last_telemetry) < m_cfg.telemetry_interval_ms / 1000)
            return;

        m_last_telemetry = now;

        string payload = JsonBuildTelemetry(symbol, event_type, detail, price, ticket);
        ApiResponse res = ApiPostTelemetry(m_cfg, payload);

        if (!res.ok && m_cfg.verbose_log)
            PrintFormat("[Telemetry] Failed to POST — code=%d", res.http_code);
    }

    //── Send heartbeat unconditionally (caller controls interval) ──
    void SendHeartbeat(const string symbol,
                       const string status,
                       const int    open_positions,
                       const double equity,
                       const double balance)
    {
        if (!m_enabled) return;

        string payload = JsonBuildHeartbeat(symbol, status, open_positions, equity, balance);
        ApiResponse res = ApiPostHeartbeat(m_cfg, payload);

        _LocalLog(TLOG_HEART, symbol,
                  StringFormat("status=%s open=%d eq=%.2f bal=%.2f → server=%s",
                               status, open_positions, equity, balance,
                               res.ok ? "OK" : "FAILED"),
                  0, 0);
    }

    //── Send trade execution report ────────────────────────────────
    void SendReport(const string symbol,
                    const string action,
                    const long   ticket,
                    const double lot,
                    const double entry,
                    const double sl,
                    const double tp,
                    const string reason)
    {
        if (!m_enabled) return;

        string payload = JsonBuildReport(symbol, action, ticket, lot, entry, sl, tp, reason);
        ApiResponse res = ApiPostReport(m_cfg, payload);

        _LocalLog(TLOG_EXEC, symbol,
                  StringFormat("action=%s ticket=%I64d lot=%.2f entry=%.5f → server=%s",
                               action, ticket, lot, entry,
                               res.ok ? "OK" : "FAILED"),
                  entry, ticket);
    }

private:
    void _LocalLog(const string level,
                   const string symbol,
                   const string message,
                   const double price,
                   const long   ticket)
    {
        if (ticket > 0)
            PrintFormat("[AMRO|%s|%s] %s | price=%.5f ticket=%I64d",
                        level, symbol, message, price, ticket);
        else if (price > 0)
            PrintFormat("[AMRO|%s|%s] %s | price=%.5f",
                        level, symbol, message, price);
        else
            PrintFormat("[AMRO|%s|%s] %s", level, symbol, message);
    }
};

#endif // AMRO_TELEMETRY_LOGGER_MQH
