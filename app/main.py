"""
AMRO SaaS — FastAPI Application Entry Point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from loguru import logger
import uvicorn, os

from app.core.config import settings
from app.api import signals, payments, candles, pipeline, ea_bridge

# ── App Init ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AMRO — AI Trading Intelligence",
    description="Market Behavior Intelligence & Audit Engine",
    version="0.1.0",
    docs_url="/docs" if settings.APP_ENV == "development" else None,
    redoc_url="/redoc" if settings.APP_ENV == "development" else None,
    openapi_url="/openapi.json" if settings.APP_ENV == "development" else None,
)

# ── CORS ─────────────────────────────────────────────────────────────────────

def _cors_origins() -> list[str]:
    if settings.APP_ENV == "production":
        return [settings.FRONTEND_URL.rstrip("/")]
    return ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── API Routers ───────────────────────────────────────────────────────────────

app.include_router(signals.router)
app.include_router(payments.router)
app.include_router(candles.router)
app.include_router(pipeline.router)
app.include_router(ea_bridge.router)

# ── Health Check ─────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "env": settings.APP_ENV, "version": "0.1.0"}

# ── Frontend (serve last — catches everything else) ───────────────────────────

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

if os.path.isdir(FRONTEND_DIR):
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    @app.get("/", include_in_schema=False)
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str = ""):
        # API routes handled above — only catch non-API paths
        if (
            full_path.startswith("api/")
            or full_path == "health"
            or full_path in {"docs", "redoc", "openapi.json"}
        ):
            from fastapi import HTTPException
            raise HTTPException(404)
        index = os.path.join(FRONTEND_DIR, "index.html")
        if os.path.exists(index):
            return FileResponse(index)
        return {"error": "Frontend not found"}
else:
    logger.warning("frontend/ not found — only API mode active")

# ── Run ───────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting AMRO on {settings.APP_HOST}:{settings.APP_PORT}")
    uvicorn.run(
        "app.main:app",
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        reload=settings.APP_ENV == "development",
    )
