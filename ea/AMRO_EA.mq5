//+------------------------------------------------------------------+
//| AMRO_EA.mq5 — Constitutional Execution Body v2.0                 |
//|                                                                  |
//| Identity:                                                        |
//|   execution body, telemetry collector, communication bridge,    |
//|   runtime observer, emergency protection layer                   |
//|                                                                  |
//| Role:                                                            |
//|   EXECUTOR — not intelligence, not analyst, not judge.           |
//|   Brains decide. EA executes. EA does NOT override.              |
//|                                                                  |
//| Constitutional Rules:                                            |
//|   - Execute only what Brain 3 approved                           |
//|   - Never modify SL/TP without server instruction                |
//|   - Emergency protection is mandatory — never disable internally |
//|   - Dry-run mode must be honoured at all times                   |
//|   - Stale signals are rejected, not executed                     |
//|   - Server silence = execution freeze                            |
//+------------------------------------------------------------------+
#property copyright "AMRO AI"
#property version   "2.00"
#property strict

#include <AMRO/JsonParser.mqh>
#include <AMRO/ConfigManager.mqh>
#include <AMRO/ApiClient.mqh>
#include <AMRO/TelemetryLogger.mqh>
#include <AMRO/HeartbeatMonitor.mqh>
#include <AMRO/RiskGuard.mqh>
#include <AMRO/ExecutionEngine.mqh>

//+------------------------------------------------------------------+
//| External Inputs — all configuration in one place                 |
//+------------------------------------------------------------------+
input group "── API Connection ──────────────────────"
input string   InpApiBaseUrl         = "http://127.0.0.1:8000"; // Server URL
input string   InpApiKey             = "";                       // API Key (optional)
input int      InpRequestTimeoutMs   = 8000;                    // Request timeout (ms)
input int      InpMaxRetries         = 2;                        // Retry attempts

input group "── Polling Intervals ───────────────────"
input int      InpDecisionPollMs     = 5000;     // Decision poll interval (ms)
input int      InpHeartbeatMs        = 15000;    // Heartbeat interval (ms)
input int      InpTelemetryMs        = 10000;    // Telemetry interval (ms)

input group "── Risk Guards ─────────────────────────"
input double   InpMaxSpreadPoints    = 30.0;     // Max spread (points, 0=disabled)
input double   InpMaxSlippagePoints  = 10.0;     // Max slippage (points)
input int      InpStaleSignalSec     = 120;      // Reject signals older than (sec)
input bool     InpEmergencyClose     = false;    // Emergency close all NOW

input group "── Execution ───────────────────────────"
input double   InpBaseLot            = 0.01;     // Base lot size
input bool     InpDryRun             = true;     // Dry-run (no real orders)
input string   InpSymbolWhitelist    = "";       // Allowed symbols (empty=all)
input int      InpMagicNumber        = 202400;   // Magic number

input group "── Logging ─────────────────────────────"
input bool     InpVerboseLog         = false;    // Verbose log output

//+------------------------------------------------------------------+
//| Module instances                                                  |
//+------------------------------------------------------------------+
AMROConfig        g_cfg;
CTelemetryLogger  g_log;
CHeartbeatMonitor g_hb;
CRiskGuard        g_guard;
CExecutionEngine  g_exec;

//── Timer state ───────────────────────────────────────────────────
datetime g_last_decision_poll = 0;

//── Last processed signal (prevent replay) ────────────────────────
long g_last_signal_ts = 0;

//+------------------------------------------------------------------+
//| OnInit                                                           |
//+------------------------------------------------------------------+
int OnInit()
{
    // ── Build config ──────────────────────────────────────────────
    g_cfg.api_base_url          = InpApiBaseUrl;
    g_cfg.api_key               = InpApiKey;
    g_cfg.request_timeout_ms    = InpRequestTimeoutMs;
    g_cfg.max_retries           = InpMaxRetries;
    g_cfg.decision_poll_ms      = InpDecisionPollMs;
    g_cfg.heartbeat_interval_ms = InpHeartbeatMs;
    g_cfg.telemetry_interval_ms = InpTelemetryMs;
    g_cfg.max_spread_points     = InpMaxSpreadPoints;
    g_cfg.max_slippage_points   = InpMaxSlippagePoints;
    g_cfg.stale_signal_seconds  = InpStaleSignalSec;
    g_cfg.emergency_close_all   = InpEmergencyClose;
    g_cfg.base_lot              = InpBaseLot;
    g_cfg.dry_run               = InpDryRun;
    g_cfg.symbol_whitelist      = InpSymbolWhitelist;
    g_cfg.magic_number          = InpMagicNumber;
    g_cfg.verbose_log           = InpVerboseLog;

    // ── Validate config ───────────────────────────────────────────
    string err = ConfigValidate(g_cfg);
    if (StringLen(err) > 0)
    {
        Print("[AMRO] Config error: ", err);
        return INIT_PARAMETERS_INCORRECT;
    }

    // ── Init modules ──────────────────────────────────────────────
    g_log.Init(g_cfg);
    g_hb.Init(g_cfg, &g_log);
    g_guard.Init(g_cfg, &g_log);
    g_exec.Init(g_cfg, &g_log, &g_guard);

    // ── Emergency close on startup if toggled ─────────────────────
    if (InpEmergencyClose)
    {
        g_guard.EngageKillSwitch("Emergency close input enabled at startup");
        g_guard.CloseAllPositions(_Symbol);
    }

    ConfigPrint(g_cfg);
    g_log.Log(TLOG_INFO, _Symbol,
              StringFormat("AMRO EA v2.0 initialised | symbol=%s magic=%d dry_run=%s",
                           _Symbol, InpMagicNumber,
                           InpDryRun ? "YES" : "NO"));

    // ── Start timer (500ms resolution) ────────────────────────────
    EventSetMillisecondTimer(500);
    return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| OnDeinit                                                         |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
    EventKillTimer();
    g_log.Log(TLOG_INFO, _Symbol,
              StringFormat("AMRO EA deinit — reason=%d", reason));
}

//+------------------------------------------------------------------+
//| OnTick — lightweight, confirms price data flowing                |
//+------------------------------------------------------------------+
void OnTick()
{
    // EA does not trade from ticks — all decisions come from server.
}

//+------------------------------------------------------------------+
//| OnTimer — main control loop                                      |
//+------------------------------------------------------------------+
void OnTimer()
{
    datetime now = TimeCurrent();

    // ── Emergency close check (runtime toggle) ────────────────────
    if (g_cfg.emergency_close_all && !g_guard.IsKilled())
    {
        g_guard.EngageKillSwitch("Emergency close toggle active");
        g_guard.CloseAllPositions(_Symbol);
        return;
    }

    // ── Heartbeat ─────────────────────────────────────────────────
    g_hb.Tick(PositionsTotal(),
              AccountInfoDouble(ACCOUNT_EQUITY),
              AccountInfoDouble(ACCOUNT_BALANCE));

    // ── Decision poll ─────────────────────────────────────────────
    int poll_sec = g_cfg.decision_poll_ms / 1000;
    if ((int)(now - g_last_decision_poll) < poll_sec) return;
    g_last_decision_poll = now;

    _PollDecision();
}

//+------------------------------------------------------------------+
//| Poll /api/ea/decision and act on approved signals                |
//+------------------------------------------------------------------+
void _PollDecision()
{
    if (!g_hb.IsServerAlive())
    {
        g_log.Log(TLOG_WARN, _Symbol, "Server not alive — decision poll skipped");
        return;
    }
    if (g_guard.IsKilled()) return;

    if (!ConfigSymbolAllowed(g_cfg, _Symbol))
    {
        if (g_cfg.verbose_log)
            g_log.Log(TLOG_INFO, _Symbol, "Symbol not in whitelist — skipping");
        return;
    }

    ApiResponse res = ApiGetDecision(g_cfg, _Symbol);

    if (!res.ok)
    {
        g_hb.RecordServerFailure();
        return;
    }
    g_hb.RecordServerContact();

    // ── Parse response ────────────────────────────────────────────
    bool   approved  = JsonGetBool(res.body,   "approved");
    string direction = JsonGetString(res.body, "direction");
    double sl_price  = JsonGetDouble(res.body, "sl_price");
    double tp_price  = JsonGetDouble(res.body, "tp_price");
    double lot_scale = JsonGetDouble(res.body, "lot_scale");
    long   sig_ts    = (long)JsonGetDouble(res.body, "timestamp");
    string reason    = JsonGetString(res.body, "recommendation");

    if (g_cfg.verbose_log)
        g_log.Log(TLOG_INFO, _Symbol,
                  StringFormat("Decision received: approved=%s dir=%s sl=%.5f tp=%.5f scale=%.2f",
                               approved ? "true" : "false",
                               direction, sl_price, tp_price, lot_scale));

    // ── Not approved or abstain ────────────────────────────────────
    if (!approved || direction == "" || direction == "ABSTAIN") return;

    // ── Stale signal ───────────────────────────────────────────────
    if (sig_ts > 0 && !g_hb.IsSignalFresh(sig_ts)) return;

    // ── Duplicate signal ───────────────────────────────────────────
    if (sig_ts > 0 && sig_ts <= g_last_signal_ts)
    {
        if (g_cfg.verbose_log)
            g_log.Log(TLOG_INFO, _Symbol, "Signal already processed — skipping");
        return;
    }

    // ── Execute order ─────────────────────────────────────────────
    ulong ticket = g_exec.OpenOrder(
        _Symbol, direction, lot_scale, sl_price, tp_price, reason
    );

    if (ticket > 0 || g_cfg.dry_run)
    {
        g_last_signal_ts = sig_ts;
        g_log.SendTelemetry(_Symbol, "ORDER_OPENED", direction,
                            SymbolInfoDouble(_Symbol, SYMBOL_BID),
                            (long)ticket);
    }
}
//+------------------------------------------------------------------+
