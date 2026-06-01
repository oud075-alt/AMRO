//+------------------------------------------------------------------+
//| AMRO — RiskGuard.mqh                                             |
//| Role: emergency safety, spread gate, kill switch                 |
//| Constitutional Rule: protect capital — never bypass safety rules |
//+------------------------------------------------------------------+
#ifndef AMRO_RISK_GUARD_MQH
#define AMRO_RISK_GUARD_MQH

#include "ConfigManager.mqh"
#include "TelemetryLogger.mqh"

//+------------------------------------------------------------------+
//| RiskGuard — pre-execution safety checks                          |
//+------------------------------------------------------------------+
class CRiskGuard
{
private:
    AMROConfig       m_cfg;
    CTelemetryLogger *m_log;
    bool             m_killed;      // true = kill switch engaged

public:
    CRiskGuard() : m_killed(false) {}

    void Init(const AMROConfig &cfg, CTelemetryLogger *logger)
    {
        m_cfg    = cfg;
        m_log    = logger;
        m_killed = false;
        m_log.Log(TLOG_GUARD, _Symbol, "RiskGuard initialised");
    }

    //── Kill switch — set by emergency toggle or API command ───────
    void EngageKillSwitch(const string reason)
    {
        m_killed = true;
        m_log.Log(TLOG_GUARD, _Symbol,
                  "KILL SWITCH ENGAGED — " + reason);
        Comment("⛔ AMRO KILL SWITCH — " + reason);
    }

    void DisengageKillSwitch()
    {
        m_killed = false;
        m_log.Log(TLOG_GUARD, _Symbol, "Kill switch disengaged");
        Comment("");
    }

    bool IsKilled() const { return m_killed; }

    //── Spread check — reject if spread too wide ───────────────────
    bool SpreadAcceptable(const string symbol)
    {
        if (m_cfg.max_spread_points <= 0) return true;   // guard disabled

        long   spread   = SymbolInfoInteger(symbol, SYMBOL_SPREAD);
        double point    = SymbolInfoDouble(symbol, SYMBOL_POINT);
        double spread_p = spread * point
                          / SymbolInfoDouble(symbol, SYMBOL_POINT);
        // spread in points (raw ticks)
        bool ok = (spread <= (long)m_cfg.max_spread_points);

        if (!ok)
            m_log.Log(TLOG_GUARD, symbol,
                      StringFormat("Spread too wide: %d pts > max %.0f pts — execution blocked",
                                   (int)spread, m_cfg.max_spread_points));
        return ok;
    }

    //── Lot scale application ──────────────────────────────────────
    double ScaledLot(const double lot_scale)
    {
        double lot = NormalizeDouble(m_cfg.base_lot * lot_scale, 2);
        double min_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
        double max_lot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
        double step    = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);

        lot = MathMax(lot, min_lot);
        lot = MathMin(lot, max_lot);
        // round to step
        lot = MathRound(lot / step) * step;
        lot = NormalizeDouble(lot, 2);
        return lot;
    }

    //── Margin check — enough free margin for the order ───────────
    bool MarginSufficient(const string symbol,
                          const ENUM_ORDER_TYPE order_type,
                          const double lot,
                          const double price)
    {
        double margin_required = 0.0;
        if (!OrderCalcMargin(order_type, symbol, lot, price, margin_required))
        {
            m_log.Log(TLOG_GUARD, symbol, "Cannot calculate margin — skipping");
            return false;
        }
        double free_margin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
        bool ok = (free_margin >= margin_required * 1.05);  // 5% buffer

        if (!ok)
            m_log.Log(TLOG_GUARD, symbol,
                      StringFormat("Insufficient margin: required=%.2f available=%.2f",
                                   margin_required, free_margin));
        return ok;
    }

    //── Emergency close all positions ─────────────────────────────
    void CloseAllPositions(const string symbol)
    {
        m_log.Log(TLOG_GUARD, symbol, "EMERGENCY CLOSE ALL — initiated");

        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            ulong ticket = PositionGetTicket(i);
            if (!PositionSelectByTicket(ticket)) continue;
            if (PositionGetString(POSITION_SYMBOL) != symbol) continue;

            MqlTradeRequest req = {};
            MqlTradeResult  res = {};
            req.action   = TRADE_ACTION_DEAL;
            req.symbol   = symbol;
            req.volume   = PositionGetDouble(POSITION_VOLUME);
            req.type     = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                           ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
            req.price    = (req.type == ORDER_TYPE_SELL)
                           ? SymbolInfoDouble(symbol, SYMBOL_BID)
                           : SymbolInfoDouble(symbol, SYMBOL_ASK);
            req.deviation = (ulong)m_cfg.max_slippage_points;
            req.magic    = m_cfg.magic_number;
            req.comment  = "AMRO_EMERGENCY_CLOSE";

            if (!OrderSend(req, res))
                m_log.Log(TLOG_ERROR, symbol,
                          StringFormat("Emergency close failed: ticket=%I64u retcode=%d",
                                       ticket, res.retcode));
            else
                m_log.Log(TLOG_GUARD, symbol,
                          StringFormat("Emergency closed: ticket=%I64u", ticket));
        }
    }
};

#endif // AMRO_RISK_GUARD_MQH
