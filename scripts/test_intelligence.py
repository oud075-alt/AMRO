"""Quick runtime path test — no fake alpha brains."""
from app.intelligence.runtime_orchestrator import run_runtime

if __name__ == "__main__":
    symbol = "EURUSD=X"
    d = run_runtime(symbol, interval="1h", run_context_llm=False)
    if not d:
        print("FAIL: no decision")
    else:
        print(f"approved={d.approved} risk={d.risk_mode} reason={d.governance_reason}")
        print(f"market_state={d.market_audit.market_state} tradable={d.market_audit.tradable}")
