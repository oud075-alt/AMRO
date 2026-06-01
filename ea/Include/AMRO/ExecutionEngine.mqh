//+------------------------------------------------------------------+
//| AMRO — ExecutionEngine.mqh                                       |
//| Role: market order execution, SL/TP management, position tracking|
//| Constitutional Rule: execute what Brain 3 approved — nothing more|
//+------------------------------------------------------------------+
#ifndef AMRO_EXECUTION_ENGINE_MQH
#define AMRO_EXECUTION_ENGINE_MQH

#include "ConfigManager.mqh"
#include "TelemetryLogger.mqh"
#include "RiskGuard.mqh"

//+------------------------------------------------------------------+
//| ExecutionEngine                                                   |
//+------------------------------------------------------------------+
class CExecutionEngine
{
private:
    AMROConfig       m_cfg;
    CTelemetryLogger *m_log;
    CRiskGuard       *m_guard;
    ulong             m_last_ticket;  // ticket of last opened position

public:
    CExecutionEngine() : m_last_ticket(0) {}

    void Init(const AMROConfig &cfg,
              CTelemetryLogger *logger,
              CRiskGuard       *guard)
    {
        m_cfg   = cfg;
        m_log   = logger;
        m_guard = guard;
        m_log.Log(TLOG_INFO, _Symbol, "ExecutionEngine initialised");
    }

    ulong LastTicket() const { return m_last_ticket; }

    //── Open a new market order ────────────────────────────────────
    //   Returns ticket on success, 0 on failure
    ulong OpenOrder(const string symbol,
                    const string direction,   // "LONG" or "SHORT"
                    const double lot_scale,
                    const double sl_price,
                    const double tp_price,
                    const string reason)
    {
        // ── Dry run ───────────────────────────────────────────────
        if (m_cfg.dry_run)
        {
            m_log.Log(TLOG_EXEC, symbol,
                      StringFormat("DRY RUN — would open %s lot_scale=%.2f sl=%.5f tp=%.5f | %s",
                                   direction, lot_scale, sl_price, tp_price, reason));
            return 0;
        }

        // ── Kill / guard checks ───────────────────────────────────
        if (m_guard.IsKilled())
        {
            m_log.Log(TLOG_GUARD, symbol, "Kill switch active — order blocked");
            return 0;
        }
        if (!m_guard.SpreadAcceptable(symbol)) return 0;

        ENUM_ORDER_TYPE order_type = (direction == "LONG" || direction == "BUY")
                                     ? ORDER_TYPE_BUY
                                     : ORDER_TYPE_SELL;

        double price = (order_type == ORDER_TYPE_BUY)
                       ? SymbolInfoDouble(symbol, SYMBOL_ASK)
                       : SymbolInfoDouble(symbol, SYMBOL_BID);

        double lot = m_guard.ScaledLot(lot_scale);
        if (lot <= 0)
        {
            m_log.Log(TLOG_GUARD, symbol, "Computed lot <= 0 — order blocked");
            return 0;
        }

        if (!m_guard.MarginSufficient(symbol, order_type, lot, price)) return 0;

        // ── Existing position check (1 position per symbol rule) ──
        if (_HasOpenPosition(symbol))
        {
            m_log.Log(TLOG_INFO, symbol,
                      "Position already open — skipping duplicate order");
            return 0;
        }

        // ── Place order ───────────────────────────────────────────
        MqlTradeRequest req = {};
        MqlTradeResult  res = {};

        req.action       = TRADE_ACTION_DEAL;
        req.symbol       = symbol;
        req.volume       = lot;
        req.type         = order_type;
        req.price        = price;
        req.sl           = sl_price;
        req.tp           = tp_price;
        req.deviation    = (ulong)m_cfg.max_slippage_points;
        req.magic        = m_cfg.magic_number;
        req.comment      = "AMRO_" + direction;
        req.type_filling = ORDER_FILLING_IOC;  // ICMarkets Raw ECN

        if (!OrderSend(req, res))
        {
            m_log.Log(TLOG_ERROR, symbol,
                      StringFormat("OrderSend failed: retcode=%d — %s",
                                   res.retcode, reason));
            return 0;
        }

        m_last_ticket = res.deal;
        m_log.Log(TLOG_EXEC, symbol,
                  StringFormat("Order opened: %s ticket=%I64u lot=%.2f "
                               "price=%.5f sl=%.5f tp=%.5f",
                               direction, m_last_ticket, lot,
                               res.price, sl_price, tp_price));

        // Send report to server
        m_log.SendReport(symbol, "OPEN", (long)m_last_ticket, lot,
                         res.price, sl_price, tp_price, reason);

        return m_last_ticket;
    }

    //── Modify SL/TP on existing position ─────────────────────────
    bool ModifyPosition(const string symbol,
                        const ulong  ticket,
                        const double new_sl,
                        const double new_tp)
    {
        if (m_cfg.dry_run)
        {
            m_log.Log(TLOG_EXEC, symbol,
                      StringFormat("DRY RUN — would modify ticket=%I64u sl=%.5f tp=%.5f",
                                   ticket, new_sl, new_tp));
            return true;
        }

        if (!PositionSelectByTicket(ticket))
        {
            m_log.Log(TLOG_WARN, symbol,
                      StringFormat("Modify: ticket=%I64u not found", ticket));
            return false;
        }

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action = TRADE_ACTION_SLTP;
        req.symbol = symbol;
        req.sl     = new_sl;
        req.tp     = new_tp;
        req.position = ticket;

        bool ok = OrderSend(req, res);
        if (!ok)
            m_log.Log(TLOG_ERROR, symbol,
                      StringFormat("Modify failed: ticket=%I64u retcode=%d",
                                   ticket, res.retcode));
        else
            m_log.Log(TLOG_EXEC, symbol,
                      StringFormat("Modified: ticket=%I64u sl=%.5f tp=%.5f",
                                   ticket, new_sl, new_tp));
        return ok;
    }

    //── Close position by ticket ───────────────────────────────────
    bool ClosePosition(const string symbol,
                       const ulong  ticket,
                       const string reason)
    {
        if (m_cfg.dry_run)
        {
            m_log.Log(TLOG_EXEC, symbol,
                      StringFormat("DRY RUN — would close ticket=%I64u | %s",
                                   ticket, reason));
            return true;
        }

        if (!PositionSelectByTicket(ticket))
        {
            m_log.Log(TLOG_WARN, symbol,
                      StringFormat("Close: ticket=%I64u not found", ticket));
            return false;
        }

        double volume = PositionGetDouble(POSITION_VOLUME);
        ENUM_POSITION_TYPE pos_type =
            (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);

        MqlTradeRequest req = {};
        MqlTradeResult  res = {};
        req.action   = TRADE_ACTION_DEAL;
        req.symbol   = symbol;
        req.volume   = volume;
        req.type     = (pos_type == POSITION_TYPE_BUY)
                       ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
        req.price    = (req.type == ORDER_TYPE_SELL)
                       ? SymbolInfoDouble(symbol, SYMBOL_BID)
                       : SymbolInfoDouble(symbol, SYMBOL_ASK);
        req.deviation = (ulong)m_cfg.max_slippage_points;
        req.magic    = m_cfg.magic_number;
        req.comment  = "AMRO_CLOSE";
        req.position = ticket;

        bool ok = OrderSend(req, res);
        if (!ok)
            m_log.Log(TLOG_ERROR, symbol,
                      StringFormat("Close failed: ticket=%I64u retcode=%d",
                                   ticket, res.retcode));
        else
        {
            m_log.Log(TLOG_EXEC, symbol,
                      StringFormat("Position closed: ticket=%I64u | %s",
                                   ticket, reason));
            m_log.SendReport(symbol, "CLOSE", (long)ticket, volume,
                             res.price, 0, 0, reason);
        }
        return ok;
    }

    //── Check if AMRO has an open position on this symbol ─────────
    bool HasOpenPosition(const string symbol)
    {
        return _HasOpenPosition(symbol);
    }

    //── Get open position ticket (first found) ────────────────────
    ulong GetOpenTicket(const string symbol)
    {
        for (int i = 0; i < PositionsTotal(); i++)
        {
            ulong t = PositionGetTicket(i);
            if (!PositionSelectByTicket(t)) continue;
            if (PositionGetString(POSITION_SYMBOL) != symbol) continue;
            if (PositionGetInteger(POSITION_MAGIC) != m_cfg.magic_number) continue;
            return t;
        }
        return 0;
    }

private:
    bool _HasOpenPosition(const string symbol)
    {
        for (int i = 0; i < PositionsTotal(); i++)
        {
            ulong t = PositionGetTicket(i);
            if (!PositionSelectByTicket(t)) continue;
            if (PositionGetString(POSITION_SYMBOL) != symbol) continue;
            if (PositionGetInteger(POSITION_MAGIC) != m_cfg.magic_number) continue;
            return true;
        }
        return false;
    }
};

#endif // AMRO_EXECUTION_ENGINE_MQH
