"""
AMRO — App Configuration
โหลดค่าจาก .env อัตโนมัติ
"""
from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # App
    APP_ENV: Literal["development", "production"] = "development"
    APP_SECRET_KEY: str = "change-me"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # PocketBase
    POCKETBASE_URL: str = "http://localhost:8090"
    POCKETBASE_ADMIN_EMAIL: str = ""
    POCKETBASE_ADMIN_PASSWORD: str = ""

    # Stripe
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_MONTHLY: str = ""
    STRIPE_PRICE_ID_YEARLY: str = ""

    # OpenAI Brain 1 (Intel Sensor)
    OPENAI_API_KEY_INTEL: str = ""
    # OpenAI Brain 2 (Analyst)
    OPENAI_API_KEY: str = ""
    # OpenAI Brain 3 (Judge) — ใช้ key คนละตัวกับ Brain 2
    OPENAI_API_KEY_JUDGE: str = ""

    # AI Brains — dashboard / trial should enable full 1/2/3 stack
    AMRO_AI_BRAINS_ENABLED: bool = True
    AMRO_BRAIN2_ANALYST_LLM: bool = True
    AMRO_BRAIN3_JUDGE_LLM: bool = True

    # Finnhub (Brain 1 — Real News + Economic Calendar)
    FINNHUB_API_KEY: str = ""

    # Google Gemini (Brain 1 Intelligence) — deprecated, replaced by GPT
    GEMINI_API_KEY: str = ""

    # Binance
    BINANCE_API_KEY: str = ""
    BINANCE_SECRET_KEY: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # URLs
    FRONTEND_URL: str = "http://localhost:3000"
    WEBHOOK_BASE_URL: str = "http://localhost:8000"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
