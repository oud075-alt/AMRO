# AMRO SaaS — Quick Start

## โครงสร้างโปรเจกต์
```
amro/
├── app/
│   ├── api/
│   │   ├── signals.py       ← Dashboard runtime API
│   │   ├── pipeline.py      ← Context → Audit → Governance → EA
│   │   └── payments.py      ← Stripe checkout + webhook
│   ├── core/
│   │   ├── config.py        ← Settings จาก .env
│   │   └── tiers.py         ← Free / Subscription / Premium rules
│   ├── intelligence/
│   │   ├── market_data.py           ← Yahoo Finance + Binance
│   │   ├── context_intelligence.py  ← AI#1 News/Context
│   │   ├── market_audit.py          ← AI#2 Statistical audit
│   │   ├── audit_layer.py           ← Core audit metrics
│   │   ├── governance.py            ← AI#3 Constitutional governance
│   │   ├── runtime_orchestrator.py  ← Main execution path
│   │   ├── gemini_agent.py          ← LLM sensor (used by AI#1)
│   │   ├── finnhub_client.py        ← Real news feed
│   │   ├── regime_detector.py       ← Market regime label
│   │   └── ai_pipeline.py           ← Pipeline → EA bridge
│   ├── services/
│   │   ├── auth.py          ← PocketBase auth + tier lookup
│   │   └── payments.py      ← Stripe service
│   └── main.py              ← FastAPI app entry point
├── runtime_logs/            ← Decision audit JSONL
├── scripts/
│   └── test_intelligence.py ← ทดสอบ runtime path
├── .env.example             ← Copy → .env แล้วใส่ค่าจริง
└── requirements.txt
```

## เริ่มต้น

### 1. ติดตั้ง dependencies
```bash
pip install -r requirements.txt
```

### 2. ตั้งค่า environment
```bash
cp .env.example .env
# แก้ไข .env ใส่ค่าจริง
```
