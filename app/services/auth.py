"""
AMRO — Auth Service (PocketBase)
จัดการ user session, tier lookup, และ token verify
"""
import httpx
from loguru import logger
from fastapi import HTTPException, Header
from typing import Optional
from app.core.config import settings
from app.core.tiers import Tier


class AuthService:
    def __init__(self):
        self.base_url = settings.POCKETBASE_URL
        self._admin_token: Optional[str] = None

    async def get_admin_token(self) -> str:
        """Login as admin และ cache token (รองรับ PocketBase v0.22+ และ v0.38+)"""
        if self._admin_token:
            return self._admin_token
        async with httpx.AsyncClient() as client:
            # PocketBase v0.38+ ใช้ _superusers endpoint
            resp = await client.post(
                f"{self.base_url}/api/collections/_superusers/auth-with-password",
                json={
                    "identity": settings.POCKETBASE_ADMIN_EMAIL,
                    "password": settings.POCKETBASE_ADMIN_PASSWORD,
                }
            )
            if resp.status_code != 200:
                # fallback สำหรับ PocketBase เวอร์ชันเก่า
                resp = await client.post(
                    f"{self.base_url}/api/admins/auth-with-password",
                    json={
                        "identity": settings.POCKETBASE_ADMIN_EMAIL,
                        "password": settings.POCKETBASE_ADMIN_PASSWORD,
                    }
                )
            resp.raise_for_status()
            data = resp.json()
            self._admin_token = data.get("token") or data.get("adminToken", "")
            logger.info(f"Admin token obtained successfully")
            return self._admin_token

    async def verify_token(self, token: str) -> dict:
        """ตรวจสอบ user token และดึงข้อมูล user"""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self.base_url}/api/collections/users/auth-refresh",
                headers={"Authorization": f"Bearer {token}"}
            )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid or expired token")
            return resp.json()["record"]

    async def get_user_tier(self, user_id: str) -> Tier:
        """ดึง tier ของ user จาก PocketBase"""
        for attempt in range(2):  # retry once if admin token expired
            try:
                admin_token = await self.get_admin_token()
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{self.base_url}/api/collections/users/records/{user_id}",
                        headers={"Authorization": f"Bearer {admin_token}"}
                    )
                    if resp.status_code == 401:
                        # Admin token expired — clear cache and retry
                        self._admin_token = None
                        continue
                    if resp.status_code != 200:
                        logger.warning(f"get_user_tier: status {resp.status_code} for user {user_id}")
                        return Tier.FREE
                    data = resp.json()
                    tier_str = data.get("tier", "free")
                    logger.info(f"get_user_tier: user={user_id} tier={tier_str}")
                    return Tier(tier_str) if tier_str in Tier._value2member_map_ else Tier.FREE
            except Exception as e:
                logger.error(f"get_user_tier error: {e}")
                return Tier.FREE
        return Tier.FREE

    async def set_user_tier(self, user_id: str, tier: Tier) -> bool:
        """อัปเดต tier ของ user (เรียกจาก Stripe webhook)"""
        try:
            admin_token = await self.get_admin_token()
            async with httpx.AsyncClient() as client:
                resp = await client.patch(
                    f"{self.base_url}/api/collections/users/records/{user_id}",
                    headers={"Authorization": f"Bearer {admin_token}"},
                    json={"tier": tier.value}
                )
                return resp.status_code == 200
        except Exception as e:
            logger.error(f"set_user_tier error: {e}")
            return False


auth_service = AuthService()


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """FastAPI dependency — ดึง current user จาก Bearer token"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.split(" ")[1]
    user = await auth_service.verify_token(token)
    return user


async def get_current_tier(authorization: Optional[str] = Header(None)) -> Tier:
    """FastAPI dependency — ดึง tier ของ current user"""
    # Dev mode: ถ้าไม่มี token ให้เป็น free tier (สำหรับ local test)
    if not authorization:
        return Tier.FREE
    try:
        user = await get_current_user(authorization)
        return await auth_service.get_user_tier(user["id"])
    except HTTPException:
        return Tier.FREE
