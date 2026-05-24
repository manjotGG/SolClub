import asyncio
import base64
import base58
import hashlib
import hmac
import json
import os
import secrets
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from database.db import (
    count_nft_records,
    count_wallet_transactions,
    create_franchise,
    get_client_profile,
    get_wallet_record,
    get_merchant_analytics,
    get_merchant_nft_tracking,
    get_merchant_profile,
    get_recent_merchant_transactions,
    get_user_account_by_identifier,
    get_user_account_by_google_sub,
    get_user_account_by_username,
    get_user_account_by_wallet,
    get_primary_wallet_for_user,
    link_external_wallet,
    list_franchises,
    list_cashback_rewards,
    list_nft_records,
    list_reward_feedback,
    list_wallets_for_user,
    list_wallet_transactions,
    save_payment_request,
    save_reward_feedback,
    assign_wallet_to_user,
    upsert_client_profile,
    upsert_merchant_profile,
    upsert_user_account,
    upsert_wallet_record,
    verify_user_password,
)
from loyalty_engine.loyalty_engine import LoyaltyRulesEngine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
FINAL_UI_SCRIPT = '<script src="/ui/static/js/ui-pages.js"></script>'
UI_SESSION_COOKIE = "solclub_session"
UI_ROLE_COOKIE = "solclub_role"
UI_SESSION_TTL_SECONDS = 60 * 60 * 12

router = APIRouter(prefix="/ui", tags=["frontend-ui"])
auth_router = APIRouter(prefix="/api/auth", tags=["auth"])
page_router = APIRouter(tags=["pages"])
_google_state_store: Dict[str, float] = {}


def _app_secret() -> str:
    return os.getenv("APP_AUTH_SECRET", "dev-insecure-secret-change-in-production")


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _sign_payload(payload_bytes: bytes) -> str:
    digest = hmac.new(_app_secret().encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
    return digest


def _create_ui_session(
    role: str,
    wallet: Optional[str] = None,
    user_ref: Optional[str] = None,
    username: Optional[str] = None,
    onboarding_required: bool = False,
    ttl_seconds: int = UI_SESSION_TTL_SECONDS,
) -> str:
    now = int(time.time())
    payload = {
        "role": role,
        "wallet": wallet or "",
        "user_ref": user_ref or "",
        "username": username or "",
        "onboarding_required": bool(onboarding_required),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    token = f"{_b64url(payload_bytes)}.{_sign_payload(payload_bytes)}"
    return token


def parse_ui_session_token(token: Optional[str]) -> Optional[Dict[str, Any]]:
    if not token or "." not in token:
        return None
    try:
        encoded_payload, signature = token.split(".", 1)
        payload_bytes = _b64url_decode(encoded_payload)
        expected_signature = _sign_payload(payload_bytes)
        if not hmac.compare_digest(signature, expected_signature):
            return None
        payload = json.loads(payload_bytes.decode("utf-8"))
        exp = int(payload.get("exp", 0) or 0)
        if exp <= int(time.time()):
            return None
        role = str(payload.get("role", "")).strip().lower()
        if role not in {"client", "merchant"}:
            return None
        payload["role"] = role
        payload["wallet"] = str(payload.get("wallet", "")).strip()
        payload["user_ref"] = str(payload.get("user_ref", "")).strip().lower()
        payload["username"] = str(payload.get("username", "")).strip()
        payload["onboarding_required"] = bool(payload.get("onboarding_required", False))
        return payload
    except Exception:
        return None


def get_ui_session_from_request(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(UI_SESSION_COOKIE)
    return parse_ui_session_token(token)


def _set_ui_session_cookies(
    response: Response,
    role: str,
    wallet: Optional[str] = None,
    user_ref: Optional[str] = None,
    username: Optional[str] = None,
    onboarding_required: bool = False,
):
    token = _create_ui_session(
        role=role,
        wallet=wallet,
        user_ref=user_ref,
        username=username,
        onboarding_required=onboarding_required,
    )
    response.set_cookie(
        UI_SESSION_COOKIE,
        token,
        max_age=UI_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    response.set_cookie(
        UI_ROLE_COOKIE,
        role,
        max_age=UI_SESSION_TTL_SECONDS,
        httponly=False,
        samesite="lax",
        secure=False,
        path="/",
    )


def _wallet_fernet_key() -> bytes:
    key = os.getenv("WALLET_ENCRYPTION_KEY", "").strip()
    if key:
        return key.encode("utf-8")
    # Deterministic fallback for local/dev environments.
    derived = hashlib.sha256(_app_secret().encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def _render_static_template(template_name: str, page_id: str, role: str, title: str) -> HTMLResponse:
    template_path = Path(TEMPLATES_DIR) / template_name
    if not template_path.exists():
        raise HTTPException(status_code=404, detail=f"Template not found: {template_name}")

    html = template_path.read_text(encoding="utf-8")
    html = re.sub(
        r"<body([^>]*)>",
        lambda match: f'<body{match.group(1)} data-page="{page_id}" data-role="{role}">',
        html,
        count=1,
        flags=re.IGNORECASE,
    )
    if FINAL_UI_SCRIPT not in html:
        html = re.sub(r"</body>", f"    {FINAL_UI_SCRIPT}\n</body>", html, count=1, flags=re.IGNORECASE)

    response = HTMLResponse(content=html)
    response.headers["Cache-Control"] = "no-store"
    return response


def _json_sse(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data, default=str)}\\n\\n"


def _role_dashboard_path(role: str) -> str:
    return "/dashboard"


def _role_ui_page(role: str) -> str:
    return "/ui/merchant" if role == "merchant" else "/ui/client"


def _client_snapshot(wallet: str, merchant_id: int) -> Dict[str, Any]:
    normalized_wallet = wallet.strip()
    rewards = list_cashback_rewards(normalized_wallet, merchant_id=merchant_id, limit=100)
    txs = list_wallet_transactions(normalized_wallet, limit=200)
    nfts = list_nft_records(normalized_wallet)

    engine = LoyaltyRulesEngine(use_sqlite=False)
    tier = engine.calculate_tier(len(txs))
    milestone = engine.get_next_milestone(len(txs))

    total_spent = round(sum(float(t.get("amount", 0) or 0) for t in txs), 6)
    total_cashback = round(sum(float(r.get("cashback_amount", 0) or 0) for r in rewards), 6)

    # Resolve username from wallet
    user = get_user_account_by_wallet(normalized_wallet)
    username = str((user or {}).get("username") or "").strip() or None

    return {
        "wallet": normalized_wallet,
        "username": username,
        "merchant_id": merchant_id,
        "tier": tier,
        "next_milestone": milestone,
        "total_transactions": len(txs),
        "total_spent": total_spent,
        "total_cashback": total_cashback,
        "nft_count": count_nft_records(normalized_wallet),
        "recent_transactions": txs[:10],
        "recent_rewards": rewards[:10],
        "recent_nfts": nfts[:10],
    }


@router.get("", response_class=HTMLResponse)
async def ui_index(request: Request):
    return _render_static_template("auth.html", "auth-onboarding", "auth", "SolClub | Enter the Arena")


@page_router.get("/", response_class=HTMLResponse)
async def landing_page(request: Request):
    return _render_static_template("index.html", "landing", "public", "SolClub | Sovereignty through Loyalty")


@router.get("/client", response_class=HTMLResponse)
async def ui_client_page(request: Request):
    return _render_static_template("client.html", "client-dashboard", "client", "SolClub | Client Dashboard")


@router.get("/client/rewards", response_class=HTMLResponse)
async def ui_client_rewards_page(request: Request):
    return _render_static_template("client_rewards.html", "client-rewards", "client", "SolClub | Rewards & Loot")


@router.get("/client/nfts", response_class=HTMLResponse)
async def ui_client_nfts_page(request: Request):
    return _render_static_template("client_nfts.html", "client-nfts", "client", "SolClub | NFT Collection")


@router.get("/client/transactions", response_class=HTMLResponse)
async def ui_client_transactions_page(request: Request):
    return _render_static_template("client_transactions.html", "client-transactions", "client", "SolClub | Transactions")


@router.get("/client/progress", response_class=HTMLResponse)
async def ui_client_progress_page(request: Request):
    return _render_static_template("client_progress.html", "client-progress", "client", "SolClub | Loyalty Progress")


@router.get("/client/feedback", response_class=HTMLResponse)
async def ui_client_feedback_page(request: Request):
    return _render_static_template("client_feedback.html", "client-feedback", "client", "SolClub | Feedback")


@router.get("/client/pay", response_class=HTMLResponse)
async def ui_client_pay_page(request: Request):
    return _render_static_template("client_pay.html", "client-pay", "client", "SolClub | Make Payment")


@router.get("/client/partners", response_class=HTMLResponse)
async def ui_client_partners_page(request: Request):
    return _render_static_template("client_partners.html", "client-partners", "client", "SolClub | Partners")


@router.get("/client/support", response_class=HTMLResponse)
async def ui_client_support_page(request: Request):
    return _render_static_template("client_support.html", "client-support", "client", "SolClub | Support")


@router.get("/client/docs", response_class=HTMLResponse)
async def ui_client_docs_page(request: Request):
    return _render_static_template("client_docs.html", "client-docs", "client", "SolClub | Documentation")


@router.get("/merchant", response_class=HTMLResponse)
async def ui_merchant_page(request: Request):
    return _render_static_template("merchant.html", "merchant-dashboard", "merchant", "SolClub Merchant Dashboard")


@router.get("/merchant/receive", response_class=HTMLResponse)
async def ui_merchant_receive_page(request: Request):
    return _render_static_template("merchant_receive.html", "merchant-receive", "merchant", "SolClub | Receive Payment")


@router.get("/merchant/cashback", response_class=HTMLResponse)
async def ui_merchant_cashback_page(request: Request):
    return _render_static_template("merchant_cashback.html", "merchant-cashback", "merchant", "SolClub | Cashback Config")


@router.get("/merchant/franchises", response_class=HTMLResponse)
async def ui_merchant_franchises_page(request: Request):
    return _render_static_template("merchant_franchises.html", "merchant-franchises", "merchant", "SolClub | Merchant Analysis")


@router.get("/merchant/analytics", response_class=HTMLResponse)
async def ui_merchant_analytics_page(request: Request):
    return _render_static_template("merchant_analytics.html", "merchant-analytics", "merchant", "SolClub | Analytics Dashboard")


@router.get("/merchant/nfts", response_class=HTMLResponse)
async def ui_merchant_nft_page(request: Request):
    return _render_static_template("merchant_nfts.html", "merchant-nfts", "merchant", "SolClub | NFT Distribution")


@router.get("/merchant/feedback", response_class=HTMLResponse)
async def ui_merchant_feedback_page(request: Request):
    return _render_static_template("merchant_feedback.html", "merchant-feedback", "merchant", "SolClub | Merchant Feedback")


@router.get("/auth", response_class=HTMLResponse)
async def ui_auth_page(request: Request):
    return _render_static_template("auth.html", "auth", "auth", "SolClub | Enter the Arena")


@page_router.get("/auth", response_class=HTMLResponse)
async def auth_page(request: Request):
    return _render_static_template("auth.html", "auth", "auth", "SolClub | Enter the Arena")


@router.get("/login", response_class=HTMLResponse)
async def ui_login_page(request: Request):
    return _render_static_template("login.html", "auth-login", "auth", "SolClub | Login")


@page_router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return _render_static_template("login.html", "auth-login", "auth", "SolClub | Login")


@router.get("/onboarding", response_class=HTMLResponse)
async def ui_onboarding_page(request: Request):
    return _render_static_template("onboarding.html", "onboarding", "auth", "SolClub | Onboarding")


@page_router.get("/onboarding", response_class=HTMLResponse)
async def onboarding_page(request: Request):
    return _render_static_template("onboarding.html", "onboarding", "auth", "SolClub | Onboarding")


@router.get("/dashboard")
async def ui_dashboard(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return RedirectResponse(url="/auth", status_code=303)
    return RedirectResponse(url=_role_ui_page(str(session.get("role") or "client")), status_code=303)


@page_router.get("/dashboard")
async def dashboard(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return RedirectResponse(url="/auth", status_code=303)
    return RedirectResponse(url=_role_ui_page(str(session.get("role") or "client")), status_code=303)


@router.get("/portal", response_class=HTMLResponse)
async def ui_portal_page(request: Request):
    return _render_static_template("role_gateway.html", "role-gateway", "auth", "SolClub | Access Portal")


@router.get("/api/client/{wallet}/snapshot")
async def ui_client_snapshot(wallet: str, merchant_id: int = 1):
    return _client_snapshot(wallet, merchant_id)


@router.get("/api/client/{wallet}/rewards")
async def ui_client_rewards(wallet: str, merchant_id: Optional[int] = None, limit: int = 100):
    return {
        "wallet": wallet.strip(),
        "items": list_cashback_rewards(wallet.strip(), merchant_id=merchant_id, limit=limit),
    }


@router.get("/api/client/{wallet}/nfts")
async def ui_client_nfts(wallet: str):
    return {"wallet": wallet.strip(), "items": list_nft_records(wallet.strip())}


@router.get("/api/client/{wallet}/transactions")
async def ui_client_transactions(wallet: str, limit: int = 50):
    return {"wallet": wallet.strip(), "items": list_wallet_transactions(wallet.strip(), limit=limit)}


@router.get("/api/client/{wallet}/progress")
async def ui_client_progress(wallet: str, merchant_id: int = 1):
    snapshot = _client_snapshot(wallet, merchant_id)
    tx_count = int(snapshot.get("total_transactions", 0))
    engine = LoyaltyRulesEngine(use_sqlite=False)
    preview = engine.evaluate_cashback_and_nft(wallet=wallet.strip(), merchant_id=merchant_id, transaction_amount=0.01)
    return {
        "wallet": wallet.strip(),
        "tier": snapshot.get("tier"),
        "next_milestone": snapshot.get("next_milestone"),
        "transactions": tx_count,
        "next_reward_tier": preview.reward_tier,
        "next_cashback_rate": preview.cashback_rate,
    }


@router.get("/api/client/{wallet}/reward-preview")
async def ui_reward_preview(wallet: str, merchant_id: int = 1, amount: float = 0.01):
    engine = LoyaltyRulesEngine(use_sqlite=False)
    decision = engine.evaluate_cashback_and_nft(wallet=wallet.strip(), merchant_id=merchant_id, transaction_amount=amount)
    return {
        "wallet": decision.wallet,
        "merchant_id": decision.merchant_id,
        "weekly_transaction_count": decision.weekly_transaction_count,
        "reward_tier": decision.reward_tier,
        "cashback_rate": decision.cashback_rate,
        "cashback_amount": decision.cashback_amount,
        "nft_rarity": decision.nft_rarity,
    }


@router.post("/api/client/{wallet}/feedback")
async def ui_feedback(wallet: str, payload: Dict[str, Any]):
    merchant_id = int(payload.get("merchant_id", 1))
    rating = int(payload.get("rating", 5))
    message = payload.get("message")
    save_reward_feedback(wallet.strip(), merchant_id, rating, message)
    return {"success": True, "wallet": wallet.strip(), "merchant_id": merchant_id}


@router.get("/api/merchant/{merchant_id}/analytics")
async def ui_merchant_analytics(merchant_id: int):
    analytics = get_merchant_analytics(merchant_id)
    analytics["recent_transactions"] = get_recent_merchant_transactions(merchant_id, limit=5)
    return analytics


@router.get("/api/merchant/{merchant_id}/feedback")
async def ui_merchant_feedback(merchant_id: int, limit: int = 50):
    return {"merchant_id": merchant_id, "items": list_reward_feedback(merchant_id, limit=limit)}


@router.get("/api/merchant/{merchant_id}/nfts")
async def ui_merchant_nfts(merchant_id: int, limit: int = 100):
    return {"merchant_id": merchant_id, "items": get_merchant_nft_tracking(merchant_id, limit=limit)}


@router.get("/api/merchant/{merchant_id}/cashback-config")
async def ui_merchant_cashback_get(merchant_id: int):
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return profile


@router.post("/api/merchant/{merchant_id}/cashback-config")
async def ui_merchant_cashback_post(merchant_id: int, payload: Dict[str, Any]):
    upsert_merchant_profile(
        merchant_id=merchant_id,
        name=str(payload.get("name", f"merchant-{merchant_id}")),
        cashback_pool_percentage=float(payload.get("cashback_pool_percentage", 2.0)),
        max_cashback_limit=float(payload.get("max_cashback_limit", 0.05)),
        weekly_distribution_rules=payload.get("weekly_distribution_rules", {"base_rate": 0.01, "tiers": []}),
    )
    return {"success": True, "merchant_id": merchant_id}


@router.get("/api/merchant/{merchant_id}/franchises")
async def ui_merchant_franchises_get(merchant_id: int):
    return {"merchant_id": merchant_id, "items": list_franchises(merchant_id)}


@router.post("/api/merchant/{merchant_id}/franchises")
async def ui_merchant_franchises_post(merchant_id: int, payload: Dict[str, Any]):
    name = str(payload.get("franchise_name", "")).strip()
    location = payload.get("location")
    if not name:
        raise HTTPException(status_code=400, detail="franchise_name is required")
    franchise = create_franchise(merchant_id, name, location)
    return {"success": True, "franchise": franchise}


@router.post("/api/wallet/connect")
@auth_router.post("/wallet/connect")
async def ui_wallet_connect(payload: Dict[str, Any], request: Request, response: Response):
    wallet = str(payload.get("wallet_address", "")).strip()
    if not wallet:
        raise HTTPException(status_code=400, detail="wallet_address is required")
    try:
        Pubkey.from_string(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

    user_role = str(payload.get("user_role", "client")).strip().lower()
    if user_role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="user_role must be either 'client' or 'merchant'")

    # Check if user is already authenticated with a username
    session = get_ui_session_from_request(request)
    session_username = str((session or {}).get("username") or "").strip() if session else ""

    if session_username:
        # Already onboarded user — link this wallet to their account
        link_external_wallet(session_username, wallet, network=str(payload.get("network", "testnet")))
        if user_role == "client":
            upsert_client_profile(wallet, username=session_username)
        _set_ui_session_cookies(
            response,
            role=user_role,
            wallet=wallet,
            username=session_username,
            onboarding_required=False,
        )
        return {
            "success": True,
            "wallet": wallet,
            "role": user_role,
            "next": _role_dashboard_path(user_role),
            "linked_to": session_username,
        }

    # Not authenticated or no username yet — original flow
    upsert_wallet_record(
        wallet_address=wallet,
        network=str(payload.get("network", "testnet")),
        provider=payload.get("provider"),
        is_primary=True,
        managed_wallet=False,
    )

    user = get_user_account_by_wallet(wallet)
    onboarding_required = not bool(user)
    username = str((user or {}).get("username") or (user or {}).get("display_name") or "").strip() or None
    if user_role == "client" and user:
        upsert_client_profile(wallet)

    _set_ui_session_cookies(
        response,
        role=user_role,
        wallet=wallet,
        user_ref=(str(user.get("email")).strip().lower() if user and user.get("email") else None),
        username=username,
        onboarding_required=onboarding_required,
    )

    return {
        "success": True,
        "wallet": wallet,
        "role": user_role,
        "next": "/onboarding" if onboarding_required else "/dashboard",
    }


@router.post("/api/wallet/auto-create")
@auth_router.post("/wallet/create")
async def ui_wallet_auto_create(payload: Dict[str, Any], response: Response):
    network = str(payload.get("network", "testnet")).lower()
    if network != "testnet":
        raise HTTPException(status_code=400, detail="Managed wallet creation is enabled for testnet only")

    keypair = Keypair()
    wallet_address = str(keypair.pubkey())
    secret_bytes = bytes(keypair)

    encrypted_secret = Fernet(_wallet_fernet_key()).encrypt(secret_bytes).decode("utf-8")
    private_key_base58 = base58.b58encode(secret_bytes).decode("utf-8")
    user_role = str(payload.get("user_role", "client")).strip().lower()
    if user_role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="user_role must be either 'client' or 'merchant'")
    upsert_wallet_record(
        wallet_address=wallet_address,
        network=network,
        provider=str(payload.get("provider", "solclub-managed")),
        is_primary=True,
        managed_wallet=True,
        encrypted_secret=encrypted_secret,
        created_by=payload.get("created_by"),
    )
    # Newly created wallets always require onboarding.
    _set_ui_session_cookies(
        response,
        role=user_role,
        wallet=wallet_address,
        username=None,
        onboarding_required=True,
    )

    return {
        "success": True,
        "wallet_address": wallet_address,
        "public_key": wallet_address,
        "private_key_base58": private_key_base58,
        "network": network,
        "managed_wallet": True,
        "role": user_role,
        "next": "/onboarding",
    }


@router.get("/api/auth/google/start")
@auth_router.get("/google/start")
async def ui_google_start(role: str = Query(default="client")):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/ui/api/auth/google/callback")
    if redirect_uri == "http://localhost:8000/platform/auth/google/callback":
        redirect_uri = "http://localhost:8000/ui/api/auth/google/callback"
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured. Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET.")

    role = role.strip().lower()
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")

    state = secrets.token_urlsafe(24)
    _google_state_store[state] = time.time() + 600
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "state": f"{state}:{role}",
        "access_type": "online",
        "prompt": "consent",
    }
    return {"state": state, "auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"}


@router.get("/api/auth/google/callback")
@auth_router.get("/google/callback")
async def ui_google_callback(code: Optional[str] = None, state: Optional[str] = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_parts = state.split(":")
    state_key = state_parts[0]
    role = state_parts[1] if len(state_parts) > 1 else "client"
    role = str(role).strip().lower()
    if role not in {"client", "merchant"}:
        role = "client"

    expires_at = _google_state_store.pop(state_key, None)
    if not expires_at or time.time() > expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/ui/api/auth/google/callback")
    if redirect_uri == "http://localhost:8000/platform/auth/google/callback":
        redirect_uri = "http://localhost:8000/ui/api/auth/google/callback"
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth credentials not configured")

    token_res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        },
        timeout=20,
    )
    if token_res.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {token_res.text}")

    token_data = token_res.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=400, detail="Google token response missing access_token")

    user_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    if user_res.status_code >= 400:
        raise HTTPException(status_code=400, detail=f"Google profile fetch failed: {user_res.text}")

    profile = user_res.json()
    google_email = str(profile.get("email") or "").strip().lower()
    google_sub = str(profile.get("sub") or "").strip()
    existing_account = get_user_account_by_google_sub(google_sub) or (get_user_account_by_identifier(google_email) if google_email else None)
    existing_username = str((existing_account or {}).get("username") or "").strip() or None

    # If the user already has a username, upsert. Otherwise skip account creation and go to onboarding.
    wallet = ""
    username = existing_username or ""
    onboarding_required = not bool(existing_username)

    if existing_username:
        account = upsert_user_account(
            email=google_email,
            username=existing_username,
            display_name=profile.get("name"),
            role=role,
            google_sub=google_sub or None,
        )
        wallet_record = get_primary_wallet_for_user(existing_username)
        wallet = (wallet_record or {}).get("wallet_address") or ""
        username = str(account.get("username") or "").strip()

    redirect = "/onboarding" if onboarding_required else _role_dashboard_path(role)
    response = RedirectResponse(url=redirect, status_code=303)
    _set_ui_session_cookies(
        response,
        role=role,
        wallet=wallet,
        user_ref=google_email,
        username=(username or None),
        onboarding_required=onboarding_required,
    )
    return response


@router.get("/api/auth/onboarding-status")
@auth_router.get("/onboarding-status")
async def ui_onboarding_status(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return {
            "authenticated": False,
            "requires_details": False,
            "role": None,
            "wallet": None,
            "redirect": "/auth",
        }

    role = str(session.get("role") or "client").strip().lower()
    wallet = str(session.get("wallet") or "").strip()
    user_ref = str(session.get("user_ref") or "").strip().lower()
    session_username = str(session.get("username") or "").strip()
    onboarding_required_flag = bool(session.get("onboarding_required", False))

    user = get_user_account_by_wallet(wallet) if wallet else None
    if not user and user_ref:
        user = get_user_account_by_identifier(user_ref)

    resolved_username = str((user or {}).get("username") or (user or {}).get("display_name") or session_username or "").strip()
    has_user_profile = bool(resolved_username)
    has_client_profile = bool(wallet and get_client_profile(wallet)) if (role == "client" and wallet) else True
    requires_details = bool(onboarding_required_flag or (not has_user_profile) or (not has_client_profile and role == "client" and wallet))

    return {
        "authenticated": True,
        "role": role,
        "wallet": wallet,
        "username": resolved_username or None,
        "user_ref": user_ref or (str(user.get("email")) if user and user.get("email") else None),
        "has_user_profile": has_user_profile,
        "has_client_profile": has_client_profile,
        "requires_details": requires_details,
        "redirect": "/onboarding" if requires_details else _role_dashboard_path(role),
    }


@router.post("/api/auth/register")
@auth_router.post("/onboarding/complete")
async def ui_register(payload: Dict[str, Any], request: Request, response: Response):
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authenticate first using wallet or Google sign-in")

    email = str(payload.get("email", "")).strip().lower()
    username = str(payload.get("username") or payload.get("display_name") or "").strip()
    display_name = username
    role = str(payload.get("role") or session.get("role") or "client").strip().lower()
    wallet = str(payload.get("wallet_address") or session.get("wallet") or "").strip()

    if not username:
        raise HTTPException(status_code=400, detail="username is required")
    if not re.match(r"^[a-zA-Z0-9_]{3,32}$", username):
        raise HTTPException(status_code=400, detail="username must be 3-32 chars (letters, numbers, underscore)")
    if email and "@" not in email:
        raise HTTPException(status_code=400, detail="email must be valid when provided")
    if not email:
        email = str(session.get("user_ref") or "").strip().lower()
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")

    account = upsert_user_account(
        email=(email or None),
        username=username,
        display_name=display_name,
        role=role,
        google_sub=str(payload.get("google_sub", "")).strip() or None,
        password=str(payload.get("password", "")).strip() or None,
    )

    if wallet:
        try:
            Pubkey.from_string(wallet)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid wallet address")

        existing_wallet = get_wallet_record(wallet)
        if not existing_wallet:
            upsert_wallet_record(
                wallet_address=wallet,
                network=str(payload.get("network", "testnet")),
                provider=str(payload.get("provider", "manual")),
                username=username,
                is_primary=True,
                managed_wallet=False,
            )
        assign_wallet_to_user(wallet, username)
        if role == "client":
            upsert_client_profile(wallet)

    _set_ui_session_cookies(
        response,
        role=role,
        wallet=wallet or "",
        user_ref=(email or None),
        username=username,
        onboarding_required=False,
    )
    return {
        "success": True,
        "account": account,
        "username": username,
        "wallet": wallet or None,
        "redirect": _role_dashboard_path(role),
    }


@router.post("/api/auth/session-role")
@auth_router.post("/session-role")
async def ui_set_session_role(payload: Dict[str, Any], request: Request, response: Response):
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")

    role = str(payload.get("role", "client")).strip().lower()
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")
    wallet = session.get("wallet")
    user_ref = str(session.get("user_ref") or "").strip().lower() or None
    onboarding_required = bool(session.get("onboarding_required", False))
    _set_ui_session_cookies(
        response,
        role=role,
        wallet=wallet,
        user_ref=user_ref,
        onboarding_required=onboarding_required,
    )
    return {"success": True, "role": role}


@router.post("/api/auth/session/start")
@auth_router.post("/session/start")
async def ui_start_session(payload: Dict[str, Any], response: Response):
    role = str(payload.get("role", "client")).strip().lower()
    wallet = str(payload.get("wallet_address", "")).strip()
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")
    if not wallet:
        raise HTTPException(status_code=400, detail="wallet_address is required")
    try:
        Pubkey.from_string(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    wallet_record = get_wallet_record(wallet)
    if not wallet_record:
        raise HTTPException(status_code=403, detail="Wallet not registered. Connect or create wallet first.")
    onboarding = {
        "has_user_profile": False,
        "has_client_profile": True,
        "requires_details": True,
    }
    user = get_user_account_by_wallet(wallet)
    if user:
        onboarding["has_user_profile"] = bool(user.get("email") and user.get("display_name"))
    onboarding["requires_details"] = not onboarding["has_user_profile"]

    _set_ui_session_cookies(
        response,
        role=role,
        wallet=wallet,
        user_ref=(str(user.get("email")).strip().lower() if user and user.get("email") else None),
        onboarding_required=onboarding["requires_details"],
    )

    redirect = "/onboarding" if onboarding["requires_details"] else _role_dashboard_path(role)
    return {
        "success": True,
        "role": role,
        "wallet": wallet,
        "redirect": redirect,
        **onboarding,
    }


@router.post("/api/auth/logout")
@auth_router.post("/logout")
async def ui_logout(response: Response):
    response.delete_cookie(UI_SESSION_COOKIE, path="/")
    response.delete_cookie(UI_ROLE_COOKIE, path="/")
    return {"success": True}


@router.get("/api/auth/session")
@auth_router.get("/session")
async def ui_get_session_role(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return {"authenticated": False, "role": None, "wallet": None, "username": None}
    wallet = str(session.get("wallet") or "").strip()
    username = str(session.get("username") or "").strip()
    # Resolve wallet from DB if session has username but no wallet
    if not wallet and username:
        wallet_record = get_primary_wallet_for_user(username)
        wallet = (wallet_record or {}).get("wallet_address") or ""
    # Resolve username from wallet if missing
    if wallet and not username:
        user = get_user_account_by_wallet(wallet)
        username = str((user or {}).get("username") or "").strip()
    return {
        "authenticated": True,
        "role": session.get("role"),
        "wallet": wallet,
        "username": username,
        "expires_at": session.get("exp"),
    }


@router.post("/api/auth/login")
@auth_router.post("/login")
async def ui_login(payload: Dict[str, Any], response: Response):
    identifier = str(payload.get("identifier", "")).strip()
    password = str(payload.get("password", "")).strip()
    role = str(payload.get("role", "client")).strip().lower()

    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")
    if not identifier:
        raise HTTPException(status_code=400, detail="identifier is required")
    if not password:
        raise HTTPException(status_code=400, detail="password is required")

    wallet = ""
    user = None
    wallet_like = re.match(r"^[1-9A-HJ-NP-Za-km-z]{32,44}$", identifier)
    if wallet_like:
        wallet = identifier
        user = get_user_account_by_wallet(wallet)
        if not user:
            raise HTTPException(status_code=404, detail="Wallet not registered")
    else:
        user = get_user_account_by_identifier(identifier)
        if user:
            uname = str(user.get("username") or "").strip()
            wallet_record = get_primary_wallet_for_user(uname) if uname else None
            wallet = (wallet_record or {}).get("wallet_address") or ""

    if not user:
        raise HTTPException(status_code=404, detail="Account not found")
    stored_hash = user.get("password_hash")
    stored_salt = user.get("password_salt")
    if stored_hash and stored_salt and not verify_user_password(user, password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    resolved_role = str(user.get("role") or role).strip().lower()
    if resolved_role not in {"client", "merchant"}:
        resolved_role = role if role in {"client", "merchant"} else "client"

    _set_ui_session_cookies(
        response,
        role=resolved_role,
        wallet=wallet,
        user_ref=(str(user.get("email")).strip().lower() if user and user.get("email") else None),
        onboarding_required=False,
    )
    return {
        "success": True,
        "role": resolved_role,
        "wallet": wallet,
        "redirect": _role_dashboard_path(resolved_role),
    }


@router.post("/api/auth/payment/create")
@auth_router.post("/payment/create")
async def ui_payment_create(payload: Dict[str, Any], request: Request):
    """Merchant creates a dynamic payment request with amount."""
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    merchant_wallet = str(payload.get("merchant_wallet", session.get("wallet", ""))).strip()
    if not merchant_wallet:
        raise HTTPException(status_code=400, detail="merchant_wallet is required")
    amount = float(payload.get("amount", 0))
    if amount <= 0:
        raise HTTPException(status_code=400, detail="amount must be positive")
    label = str(payload.get("label", "SolClub Payment")).strip()

    import uuid
    reference = str(uuid.uuid4())[:12]
    save_payment_request(
        reference=reference,
        user_wallet=merchant_wallet,
        store_id=str(payload.get("store_id", "solclub")),
        status="pending",
        qr_type="dynamic",
        amount=amount,
    )
    return {
        "success": True,
        "reference": reference,
        "merchant_wallet": merchant_wallet,
        "amount": amount,
        "label": label,
        "status": "pending",
    }


@router.get("/api/auth/payment/{reference}")
@auth_router.get("/payment/{reference}")
async def ui_payment_get(reference: str):
    """Get a payment request by reference."""
    from database.db import _require_client, _require_data, _db
    _require_client()
    result = _db.client.table("payment_requests").select("*").eq("reference", reference).limit(1).execute()
    rows = _require_data(result)
    if not rows:
        raise HTTPException(status_code=404, detail="Payment request not found")
    return rows[0]


@router.post("/api/auth/payment/send")
@auth_router.post("/payment/send")
async def ui_payment_send(payload: Dict[str, Any], request: Request):
    """Client sends a payment to a merchant.

    For managed wallets the transaction is signed and broadcast on-chain.
    For external wallets a Solana Pay URL is returned so the user can
    approve the transaction in their wallet app.
    """
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    sender_wallet = str(session.get("wallet", "")).strip()
    if not sender_wallet:
        raise HTTPException(status_code=400, detail="No wallet in session. Connect a wallet first.")
    merchant_wallet = str(payload.get("merchant_wallet", "")).strip()
    amount = float(payload.get("amount", 0))
    if not merchant_wallet or amount <= 0:
        raise HTTPException(status_code=400, detail="merchant_wallet and positive amount required")

    # Validate merchant wallet address
    try:
        recipient_pubkey = Pubkey.from_string(merchant_wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid merchant wallet address")

    from database.db import insert_transaction, save_cashback_reward
    from loyalty_engine.loyalty_engine import LoyaltyRulesEngine
    import uuid

    # Check if sender wallet is a managed wallet with stored key
    wallet_record = get_wallet_record(sender_wallet)
    is_managed = bool((wallet_record or {}).get("managed_wallet") and (wallet_record or {}).get("encrypted_secret"))

    real_signature = None
    solana_pay_url = None

    if is_managed:
        # ---- Managed wallet: sign & send on-chain ----
        try:
            encrypted_secret = wallet_record["encrypted_secret"]
            secret_bytes = Fernet(_wallet_fernet_key()).decrypt(encrypted_secret.encode("utf-8"))
            sender_keypair = Keypair.from_bytes(secret_bytes)

            from solana.rpc.api import Client as SyncSolanaClient
            from solders.system_program import TransferParams, transfer
            from solders.transaction import Transaction
            from solders.message import Message

            rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.testnet.solana.com")
            sol_client = SyncSolanaClient(rpc_url)

            lamports = int(amount * 1_000_000_000)
            ix = transfer(TransferParams(
                from_pubkey=sender_keypair.pubkey(),
                to_pubkey=recipient_pubkey,
                lamports=lamports,
            ))

            # Fetch a recent blockhash
            bh_resp = sol_client.get_latest_blockhash()
            recent_blockhash = bh_resp.value.blockhash

            msg = Message.new_with_blockhash([ix], sender_keypair.pubkey(), recent_blockhash)
            tx = Transaction.new_unsigned(msg)
            tx.sign([sender_keypair], recent_blockhash)

            send_resp = sol_client.send_transaction(tx)
            real_signature = str(send_resp.value)
            print(f"✅ On-chain payment sent: {real_signature}")
        except Exception as exc:
            print(f"❌ On-chain payment failed: {exc}")
            # Fall back to DB-only record
            real_signature = None

    if not real_signature and not is_managed:
        # ---- External wallet: return Solana Pay URL ----
        ref = str(uuid.uuid4())[:12]
        solana_pay_url = f"solana:{merchant_wallet}?amount={amount}&reference={ref}&label=SolClub+Payment"
        save_payment_request(
            reference=ref, user_wallet=merchant_wallet,
            store_id="solclub", status="pending", qr_type="dynamic", amount=amount,
        )
        return {
            "success": True,
            "method": "external",
            "solana_pay_url": solana_pay_url,
            "amount": amount,
            "merchant_wallet": merchant_wallet,
            "message": "Open this URL in your Solana wallet to complete the payment.",
        }

    # Record the transaction in DB
    sig = real_signature or f"pay-{uuid.uuid4().hex[:16]}"
    insert_transaction(wallet=sender_wallet, merchant_id=1, amount=amount, signature=sig)

    engine = LoyaltyRulesEngine(use_sqlite=False)
    decision = engine.evaluate_cashback_and_nft(wallet=sender_wallet, merchant_id=1, transaction_amount=amount)
    save_cashback_reward(
        wallet=sender_wallet, merchant_id=1, transaction_signature=sig,
        transaction_amount=amount, cashback_amount=decision.cashback_amount, reward_tier=decision.reward_tier,
    )

    ref = str(payload.get("reference", "")).strip()
    if ref:
        save_payment_request(reference=ref, user_wallet=merchant_wallet, store_id="solclub", status="completed", qr_type="dynamic", amount=amount)

    return {
        "success": True,
        "method": "managed" if is_managed and real_signature else "fallback",
        "signature": sig,
        "on_chain": bool(real_signature),
        "amount": amount,
        "cashback": decision.cashback_amount,
        "tier": decision.reward_tier,
    }


@router.get("/api/auth/merchant/wallet-info")
@auth_router.get("/merchant/wallet-info")
async def ui_merchant_wallet_info(request: Request):
    """Return merchant wallet address for static QR."""
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    wallet = str(session.get("wallet", "")).strip()
    username = str(session.get("username", "")).strip()
    return {"wallet": wallet, "username": username}


@router.get("/api/wallet/{wallet}/balance")
async def ui_wallet_balance(wallet: str):
    """Fetch the SOL balance of a wallet from Solana RPC."""
    import httpx
    rpc_url = os.getenv("SOLANA_RPC_URL", "https://api.testnet.solana.com")
    try:
        Pubkey.from_string(wallet.strip())
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wallet address")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(rpc_url, json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "getBalance",
                "params": [wallet.strip()],
            })
            data = resp.json()
            lamports = int((data.get("result") or {}).get("value", 0))
            return {
                "wallet": wallet.strip(),
                "balance_lamports": lamports,
                "balance_sol": round(lamports / 1_000_000_000, 6),
            }
    except Exception as exc:
        return {"wallet": wallet.strip(), "balance_lamports": 0, "balance_sol": 0.0, "error": str(exc)}


@router.post("/api/wallet/link")
@auth_router.post("/wallet/link")
async def ui_wallet_link(payload: Dict[str, Any], request: Request):
    """Link an external real Solana wallet to the authenticated user."""
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    username = str(session.get("username") or "").strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username not set. Complete onboarding first.")
    wallet_address = str(payload.get("wallet_address", "")).strip()
    if not wallet_address:
        raise HTTPException(status_code=400, detail="wallet_address is required")
    try:
        Pubkey.from_string(wallet_address)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")
    network = str(payload.get("network", "mainnet-beta")).strip()
    record = link_external_wallet(username, wallet_address, network=network)
    return {"success": True, "wallet": record}


@router.get("/api/wallet/list")
@auth_router.get("/wallet/list")
async def ui_wallet_list(request: Request):
    """List all wallets linked to the authenticated user."""
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")
    username = str(session.get("username") or "").strip()
    if not username:
        return {"wallets": []}
    wallets = list_wallets_for_user(username)
    return {"username": username, "wallets": wallets}


@router.get("/events")
async def ui_events(
    channel: str = Query(default="client", pattern="^(client|merchant|auth)$"),
    wallet: Optional[str] = None,
    merchant_id: int = 1,
    amount: float = 0.1,
):
    async def event_stream():
        while True:
            try:
                if channel == "client":
                    if not wallet:
                        payload = {"error": "wallet query is required for client stream"}
                    else:
                        snapshot = _client_snapshot(wallet, merchant_id)
                        preview = await ui_reward_preview(wallet=wallet, merchant_id=merchant_id, amount=amount)
                        payload = {"channel": channel, "snapshot": snapshot, "preview": preview}
                elif channel == "merchant":
                    payload = {
                        "channel": channel,
                        "analytics": get_merchant_analytics(merchant_id),
                        "nfts": get_merchant_nft_tracking(merchant_id, limit=10),
                    }
                else:
                    payload = {
                        "channel": channel,
                        "timestamp": datetime.utcnow().isoformat(),
                        "wallet_count_hint": count_wallet_transactions(wallet or "") if wallet else 0,
                    }
                yield _json_sse(payload)
            except Exception as exc:
                yield _json_sse({"channel": channel, "error": str(exc)})
            await asyncio.sleep(5)

    return StreamingResponse(event_stream(), media_type="text/event-stream")
