//+------------------------------------------------------------------+
//| AMRO — HeartbeatMonitor.mqh                                      |
//| Role: watchdog — detect stale signals, lost server contact       |
//| Constitutional Rule: if the server goes silent, freeze execution |
//+------------------------------------------------------------------+
#ifndef AMRO_HEARTBEAT_MONITOR_MQH
#define AMRO_HEARTBEAT_MONITOR_MQH

#include "ConfigManager.mqh"
#include "TelemetryLogger.mqh"

//+------------------------------------------------------------------+
//| Heartbeat monitor state                                          |
//+------------------------------------------------------------------+
class CHeartbeatMonitor
{
private:
    AMROConfig       m_cfg;
    CTelemetryLogger *m_log;

    datetime  m_last_hb_sent;          // when we last sent a heartbeat
    datetime  m_last_server_contact;   // when server last replied OK
    bool      m_server_alive;          // false = no recent contact
    int       m_consecutive_failures;  // rolling failure count
    int       m_max_failures;          // threshold before declaring dead

public:
    CHeartbeatMonitor()
        : m_last_hb_sent(0), m_last_server_contact(0),
          m_server_alive(false), m_consecutive_failures(0), m_max_failures(3)
    {}

    void Init(const AMROConfig &cfg, CTelemetryLogger *logger)
    {
        m_cfg     = cfg;
        m_log     = logger;
        m_server_alive = true;    // assume alive until proven otherwise
        m_last_server_contact = TimeCurrent();
        m_log.Log(TLOG_HEART, _Symbol, "HeartbeatMonitor initialised");
    }

    //── Called on every OnTimer() tick ─────────────────────────────
    void Tick(const int open_positions,
              const double equity,
              const double balance)
    {
        datetime now = TimeCurrent();
        int interval_sec = m_cfg.heartbeat_interval_ms / 1000;

        if ((int)(now - m_last_hb_sent) < interval_sec) return;
        m_last_hb_sent = now;

        string status = m_server_alive ? "ALIVE" : "DEGRADED";
        m_log.SendHeartbeat(_Symbol, status, open_positions, equity, balance);
    }

    //── Call this when a server response is received ───────────────
    void RecordServerContact()
    {
        m_last_server_contact   = TimeCurrent();
        m_consecutive_failures  = 0;
        m_server_alive          = true;
    }

    //── Call this when a server request fails ──────────────────────
    void RecordServerFailure()
    {
        m_consecutive_failures++;
        if (m_consecutive_failures >= m_max_failures)
        {
            m_server_alive = false;
            m_log.Log(TLOG_WARN, _Symbol,
                      StringFormat("Server unreachable — %d consecutive failures. "
                                   "Execution frozen until contact restored.",
                                   m_consecutive_failures));
        }
    }

    //── Is the server considered alive? ────────────────────────────
    bool IsServerAlive() const { return m_server_alive; }

    //── Is a given signal timestamp still fresh? ───────────────────
    bool IsSignalFresh(const long signal_ts_unix)
    {
        long now    = (long)TimeGMT();   // use UTC to match server timestamp
        long age    = now - signal_ts_unix;
        bool fresh  = (age >= 0 && age <= m_cfg.stale_signal_seconds);

        if (!fresh)
            m_log.Log(TLOG_WARN, _Symbol,
                      StringFormat("Signal stale: age=%I64d sec (max=%d)",
                                   age, m_cfg.stale_signal_seconds));
        return fresh;
    }

    //── Seconds since last server contact ─────────────────────────
    int SecondsSinceContact() const
    {
        return (int)(TimeCurrent() - m_last_server_contact);
    }
};

#endif // AMRO_HEARTBEAT_MONITOR_MQH
