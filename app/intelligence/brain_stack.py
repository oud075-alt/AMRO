"""
AMRO — Brain 1 / 2 / 3 stack configuration.

Keys and enablement live here so each brain reads one place.
No separate AMRO_* feature flags in .env — only OPENAI_API_KEY_* per brain.
"""
from __future__ import annotations

from app.core.config import settings

BRAIN1_MODEL = "gpt-4o-mini"
BRAIN2_MODEL = "gpt-4o-mini"
BRAIN3_MODEL = "gpt-4o-mini"


def brain1_api_key() -> str:
    return (settings.OPENAI_API_KEY_INTEL or settings.OPENAI_API_KEY or "").strip()


def brain2_api_key() -> str:
    return (settings.OPENAI_API_KEY or settings.OPENAI_API_KEY_INTEL or "").strip()


def brain3_api_key() -> str:
    return (
        settings.OPENAI_API_KEY_JUDGE
        or settings.OPENAI_API_KEY
        or settings.OPENAI_API_KEY_INTEL
        or ""
    ).strip()


def brain1_active() -> bool:
    return bool(brain1_api_key())


def brain2_active() -> bool:
    return bool(brain2_api_key())


def brain3_active() -> bool:
    return bool(brain3_api_key())


def finnhub_active() -> bool:
    return bool((settings.FINNHUB_API_KEY or "").strip())
