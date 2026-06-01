"""
AMRO — Stripe Payment Service
จัดการ Subscription, Checkout, และ Webhook
"""
import stripe
from fastapi import HTTPException, Request
from loguru import logger
from app.core.config import settings
from app.core.tiers import Tier

stripe.api_key = settings.STRIPE_SECRET_KEY


class PaymentService:

    def create_checkout_session(
        self,
        user_id: str,
        user_email: str,
        plan: str = "monthly"      # "monthly" | "yearly"
    ) -> str:
        """สร้าง Stripe Checkout URL แล้วส่งกลับไปให้ frontend redirect"""
        price_id = (
            settings.STRIPE_PRICE_ID_YEARLY
            if plan == "yearly"
            else settings.STRIPE_PRICE_ID_MONTHLY
        )

        if not price_id:
            raise HTTPException(500, "Stripe price ID not configured")

        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card", "promptpay"],
                mode="subscription",
                line_items=[{"price": price_id, "quantity": 1}],
                customer_email=user_email,
                metadata={"user_id": user_id, "plan": plan},
                success_url=f"{settings.FRONTEND_URL}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{settings.FRONTEND_URL}/pricing",
            )
            return session.url
        except stripe.StripeError as e:
            logger.error(f"Stripe checkout error: {e}")
            raise HTTPException(500, f"Payment error: {str(e)}")

    def create_portal_session(self, customer_id: str) -> str:
        """สร้าง Stripe Customer Portal URL สำหรับจัดการ subscription"""
        try:
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{settings.FRONTEND_URL}/dashboard",
            )
            return session.url
        except stripe.StripeError as e:
            logger.error(f"Stripe portal error: {e}")
            raise HTTPException(500, str(e))

    async def handle_webhook(self, request: Request) -> dict:
        """
        รับ Webhook จาก Stripe และ update tier ใน PocketBase อัตโนมัติ

        Events ที่จัดการ:
        - checkout.session.completed    → upgrade to SUBSCRIPTION
        - customer.subscription.deleted → downgrade to FREE
        - invoice.payment_failed        → notify user
        """
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, settings.STRIPE_WEBHOOK_SECRET
            )
        except stripe.SignatureVerificationError:
            raise HTTPException(400, "Invalid webhook signature")

        event_type = event["type"]
        data = event["data"]["object"]
        logger.info(f"Stripe webhook: {event_type}")

        if event_type == "checkout.session.completed":
            user_id = data.get("metadata", {}).get("user_id")
            if user_id:
                from app.services.auth import auth_service
                await auth_service.set_user_tier(user_id, Tier.SUBSCRIPTION)
                logger.info(f"User {user_id} upgraded to SUBSCRIPTION")

        elif event_type == "customer.subscription.deleted":
            # ต้อง map customer_id → user_id (เก็บใน PocketBase)
            logger.info(f"Subscription cancelled: {data.get('id')}")
            # TODO: lookup user_id by stripe_customer_id แล้ว downgrade

        elif event_type == "invoice.payment_failed":
            logger.warning(f"Payment failed for customer: {data.get('customer')}")
            # TODO: ส่ง email แจ้งเตือน

        return {"status": "ok", "event": event_type}


payment_service = PaymentService()
