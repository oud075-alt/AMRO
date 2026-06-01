"""
AMRO — Payment API Routes
"""
from fastapi import APIRouter, Depends, Request, Query
from app.services.payments import payment_service
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/payments", tags=["payments"])


@router.post("/checkout")
async def create_checkout(
    plan: str = Query("monthly", description="monthly | yearly"),
    current_user: dict = Depends(get_current_user),
):
    """สร้าง Stripe Checkout URL"""
    url = payment_service.create_checkout_session(
        user_id=current_user["id"],
        user_email=current_user.get("email", ""),
        plan=plan,
    )
    return {"checkout_url": url}


@router.post("/webhook")
async def stripe_webhook(request: Request):
    """รับ Webhook จาก Stripe — ปลดล็อก tier อัตโนมัติ"""
    return await payment_service.handle_webhook(request)


@router.post("/portal")
async def customer_portal(current_user: dict = Depends(get_current_user)):
    """Redirect ไป Stripe Customer Portal เพื่อจัดการ subscription"""
    customer_id = current_user.get("stripe_customer_id", "")
    if not customer_id:
        return {"error": "ไม่พบ Stripe customer ID"}
    url = payment_service.create_portal_session(customer_id)
    return {"portal_url": url}
