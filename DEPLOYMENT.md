# AMRO Web Trial Deployment

This runbook deploys AMRO for browser-based trial access only. EA live execution is not enabled for this launch; the EA bridge returns governance permission/fail-closed state only.

## 1. One-Command VPS Deploy (Linode / Vultr / DO)

On a fresh Ubuntu 22.04 server as `root`:

```bash
curl -fsSL https://raw.githubusercontent.com/oud075-alt/AMRO/main/scripts/deploy_vps.sh | bash
```

Then edit API keys:

```bash
nano /opt/amro/.env
systemctl restart amro
```

Open `http://YOUR_SERVER_IP/` in a browser.

## 2. Manual Server Setup

Use Python 3.12 if possible.

```bash
cd amro
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows:

```powershell
cd amro
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 2. Environment

Copy the production template and fill real values:

```bash
cp .env.production.example .env
```

Required for public trial:

```env
APP_ENV=production
APP_SECRET_KEY=<random-32-plus-character-secret>
FRONTEND_URL=https://your-domain.com
WEBHOOK_BASE_URL=https://your-domain.com
```

Add AI/news/payment keys only for features you want active during the trial.

## 3. Run Command

Managed platform startup command:

```bash
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

VPS/process-manager startup command:

```bash
pip install gunicorn
gunicorn -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:8000 --workers 2 --timeout 120
```

## 4. Reverse Proxy / HTTPS

Put the app behind HTTPS. For Nginx, proxy the domain to `127.0.0.1:8000`.

Important:
- Forward `Host`, `X-Forwarded-For`, and `X-Forwarded-Proto`.
- Keep `FRONTEND_URL` exactly matching the public origin.
- Do not expose `.env`, `runtime_logs`, or `data/brain2/state` as static files.

## 5. Production Safety Checks

Before sharing the URL:

```bash
python -m compileall -q app
python -m app.intelligence.brain2.topic_training --topic governance_synchronization --scenario heldout_btc_china_mining_selloff_2021 --scenario-set out_of_sample --blind --reload
```

HTTP smoke checks:

```bash
curl https://your-domain.com/health
curl "https://your-domain.com/api/signals/GC=F?audit=false&interval=1h"
curl "https://your-domain.com/api/pipeline/status"
```

Expected:
- `/health` returns `{"status":"ok","env":"production"}`.
- `/docs` is not available in production.
- Dashboard loads from `/`.
- Environment panel uses `Upside pressure`, `Downside pressure`, and `Participation threshold`.
- `/api/ea/decision?symbol=GC=F` returns permission/fail-closed data, not a trade signal.
- `/api/ea/test-permission` returns 404 in production.

## 6. Rollback

If public trial fails:

1. Stop the process manager or platform deployment.
2. Restore the previous artifact/branch.
3. Restart the service.
4. Verify `/health` and dashboard load.

## 7. Launch Scope

This launch is web-only:
- Browser dashboard: enabled.
- Brain-1/2/3 runtime evaluation: enabled.
- EA live execution: disabled/not part of public trial.
- EA bridge: permission/fail-closed state only.
