"""
AMRO — Tier System
กำหนดสิทธิ์การเข้าถึงแต่ละ tier: free / subscription / premium
"""
from enum import Enum
from dataclasses import dataclass


class Tier(str, Enum):
    FREE = "free"
    SUBSCRIPTION = "subscription"
    PREMIUM = "premium"


@dataclass
class TierConfig:
    signal_delay_minutes: int    # 0 = real-time, >0 = delayed
    history_days: int            # จำนวนวันย้อนหลังที่ดูได้
    confidence_visible: bool     # เห็น confidence score เต็ม หรือถูก blur
    audit_agent: bool            # เข้าถึง Audit Agent ได้มั้ย
    regime_detection: bool       # เห็น Regime Detection มั้ย
    pdf_report: bool             # Export PDF ได้มั้ย
    api_access: bool             # เรียก API ได้มั้ย
    daily_signal_limit: int      # จำนวน signal ต่อวัน (-1 = unlimited)


TIER_CONFIG: dict[Tier, TierConfig] = {
    Tier.FREE: TierConfig(
        signal_delay_minutes=60,   # delay 1 ชั่วโมง
        history_days=7,
        confidence_visible=False,  # blur
        audit_agent=False,
        regime_detection=False,
        pdf_report=False,
        api_access=False,
        daily_signal_limit=5,
    ),
    Tier.SUBSCRIPTION: TierConfig(
        signal_delay_minutes=0,    # real-time
        history_days=90,
        confidence_visible=True,
        audit_agent=True,
        regime_detection=True,
        pdf_report=True,
        api_access=False,
        daily_signal_limit=-1,     # unlimited
    ),
    Tier.PREMIUM: TierConfig(
        signal_delay_minutes=0,
        history_days=365,
        confidence_visible=True,
        audit_agent=True,
        regime_detection=True,
        pdf_report=True,
        api_access=True,
        daily_signal_limit=-1,
    ),
}


def get_tier_config(tier: Tier) -> TierConfig:
    return TIER_CONFIG[tier]


def check_feature(tier: Tier, feature: str) -> bool:
    """ตรวจสอบว่า tier นี้เข้าถึง feature ได้มั้ย"""
    config = TIER_CONFIG[tier]
    return getattr(config, feature, False)
