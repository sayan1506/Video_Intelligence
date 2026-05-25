import os
import hmac
import hashlib
import json
import logging
import razorpay
from fastapi import APIRouter, HTTPException, Depends, Request
from services import firestore
from middleware.auth import get_current_user

router = APIRouter()
logger = logging.getLogger(__name__)


def _get_razorpay_client() -> razorpay.Client:
    """
    Lazy-init Razorpay client. Reads keys at call time, not module load.
    Follows the same pattern as os.getenv() inside functions throughout this project.
    """
    return razorpay.Client(auth=(
        os.getenv("RAZORPAY_KEY_ID"),
        os.getenv("RAZORPAY_KEY_SECRET"),
    ))


@router.post("/billing/create-checkout-session")
async def create_checkout_session(current_user: dict = Depends(get_current_user)):
    """
    Create a Razorpay Subscription for the Pro plan.
    Returns { subscriptionId, keyId } that the frontend uses to open
    Razorpay Checkout (window.Razorpay) directly in the browser.
    """
    client = _get_razorpay_client()
    user = firestore.get_or_create_user(current_user["uid"], current_user["email"])

    # If a subscription already exists and is still active, return it directly
    existing_sub_id = user.get("razorpaySubscriptionId")
    if existing_sub_id:
        try:
            sub = client.subscription.fetch(existing_sub_id)
            if sub.get("status") in ("created", "authenticated", "active"):
                logger.info(f"[{current_user['uid']}] Reusing existing subscription: {existing_sub_id}")
                return {
                    "subscriptionId": existing_sub_id,
                    "keyId": os.getenv("RAZORPAY_KEY_ID"),
                }
        except Exception:
            pass  # subscription no longer valid — create a new one

    try:
        subscription = client.subscription.create({
            "plan_id": os.getenv("RAZORPAY_PRO_PLAN_ID"),
            "total_count": 12,
            "quantity": 1,
            "notes": {
                "firebaseUid": current_user["uid"],
                "email": current_user["email"],
            },
        })
        subscription_id = subscription["id"]
        firestore.update_user(current_user["uid"], {
            "razorpaySubscriptionId": subscription_id,
        })
        logger.info(f"[{current_user['uid']}] Razorpay subscription created: {subscription_id}")
        return {
            "subscriptionId": subscription_id,
            "keyId": os.getenv("RAZORPAY_KEY_ID"),
        }
    except Exception as e:
        logger.error(f"[{current_user['uid']}] Razorpay subscription creation failed: {e}")
        raise HTTPException(status_code=500, detail="Payment service unavailable.")


@router.post("/billing/webhook")
async def razorpay_webhook(request: Request):
    """
    Razorpay sends POST events here after subscription lifecycle changes.
    This endpoint MUST NOT use get_current_user — Razorpay calls it, not the frontend.
    Signature verification via RAZORPAY_WEBHOOK_SECRET ensures the request is genuine.
    """
    payload_bytes = await request.body()
    sig_header = request.headers.get("X-Razorpay-Signature", "")
    webhook_secret = os.getenv("RAZORPAY_WEBHOOK_SECRET", "")

    # HMAC-SHA256 verification
    expected_sig = hmac.new(
        webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected_sig, sig_header):
        logger.warning("Razorpay webhook: signature verification failed")
        raise HTTPException(status_code=400, detail="Invalid webhook signature.")

    try:
        event = json.loads(payload_bytes)
    except Exception as e:
        logger.error(f"Razorpay webhook: JSON parse failed: {e}")
        raise HTTPException(status_code=400, detail="Webhook processing failed.")

    event_type = event.get("event", "")
    logger.info(f"Razorpay webhook received: {event_type}")

    if event_type == "subscription.activated":
        _handle_subscription_activated(event["payload"]["subscription"]["entity"])
    elif event_type == "subscription.cancelled":
        _handle_subscription_cancelled(event["payload"]["subscription"]["entity"])
    elif event_type == "payment.failed":
        _handle_payment_failed(event["payload"]["payment"]["entity"])

    return {"received": True}


@router.get("/billing/status")
async def billing_status(current_user: dict = Depends(get_current_user)):
    """
    Return the current user's plan.
    Called by /billing/success page to poll until the webhook has updated
    the plan from 'free' to 'pro'.
    """
    plan = firestore.get_user_plan(current_user["uid"])
    return {"plan": plan}


def _handle_subscription_activated(subscription: dict) -> None:
    subscription_id = subscription["id"]
    period_end = subscription.get("current_end")
    user = firestore.get_user_by_razorpay_subscription(subscription_id)
    if user:
        firestore.update_user(user["userId"], {
            "plan": "pro",
            "planExpiresAt": period_end,
        })
        logger.info(f"[{user['userId']}] Upgraded to Pro (period end: {period_end})")
    else:
        logger.warning(f"Webhook: no user found for Razorpay subscription {subscription_id}")


def _handle_subscription_cancelled(subscription: dict) -> None:
    subscription_id = subscription["id"]
    user = firestore.get_user_by_razorpay_subscription(subscription_id)
    if user:
        firestore.update_user(user["userId"], {"plan": "free", "planExpiresAt": None})
        logger.info(f"[{user['userId']}] Downgraded to Free (subscription cancelled)")


def _handle_payment_failed(payment: dict) -> None:
    subscription_id = payment.get("subscription_id", "")
    if not subscription_id:
        return
    user = firestore.get_user_by_razorpay_subscription(subscription_id)
    if user:
        logger.warning(f"[{user['userId']}] Payment failed (Razorpay will retry)")
