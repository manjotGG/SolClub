import asyncio
import base64
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
    get_user_account_by_identifier,
    get_user_account_by_wallet,
    get_primary_wallet_for_user,
    list_franchises,
    list_cashback_rewards,
    list_nft_records,
    list_reward_feedback,
    list_wallet_transactions,
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


def _create_ui_session(role: str, wallet: Optional[str] = None, ttl_seconds: int = UI_SESSION_TTL_SECONDS) -> str:
    now = int(time.time())
    payload = {
        "role": role,
        "wallet": wallet or "",
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
        return payload
    except Exception:
        return None


def get_ui_session_from_request(request: Request) -> Optional[Dict[str, Any]]:
    token = request.cookies.get(UI_SESSION_COOKIE)
    return parse_ui_session_token(token)


def _set_ui_session_cookies(response: Response, role: str, wallet: Optional[str] = None):
    token = _create_ui_session(role=role, wallet=wallet)
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

    return {
        "wallet": normalized_wallet,
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


@router.get("/merchant", response_class=HTMLResponse)
async def ui_merchant_page(request: Request):
    return _render_static_template("merchant.html", "merchant-dashboard", "merchant", "SolClub Merchant Dashboard")


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


@router.get("/login", response_class=HTMLResponse)
async def ui_login_page(request: Request):
    return _render_static_template("auth.html", "auth-login", "auth", "SolClub | Login")


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
    return get_merchant_analytics(merchant_id)


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
async def ui_wallet_connect(payload: Dict[str, Any], response: Response):
    wallet = str(payload.get("wallet_address", "")).strip()
    if not wallet:
        raise HTTPException(status_code=400, detail="wallet_address is required")
    try:
        Pubkey.from_string(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

    upsert_wallet_record(
        wallet_address=wallet,
        network=str(payload.get("network", "testnet")),
        provider=payload.get("provider"),
        is_primary=True,
        managed_wallet=False,
    )
    user_role = str(payload.get("user_role", "client")).strip().lower()
    if user_role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="user_role must be either 'client' or 'merchant'")

    if user_role == "client":
        upsert_client_profile(wallet)

    _set_ui_session_cookies(response, role=user_role, wallet=wallet)

    return {
        "success": True,
        "wallet": wallet,
        "role": user_role,
        "next": "/ui/auth?stage=details",
    }


@router.post("/api/wallet/auto-create")
async def ui_wallet_auto_create(payload: Dict[str, Any], response: Response):
    network = str(payload.get("network", "testnet")).lower()
    if network != "testnet":
        raise HTTPException(status_code=400, detail="Managed wallet creation is enabled for testnet only")

    keypair = Keypair()
    wallet_address = str(keypair.pubkey())
    secret_bytes = bytes(keypair)

    encrypted_secret = Fernet(_wallet_fernet_key()).encrypt(secret_bytes).decode("utf-8")
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
    if user_role == "client":
        upsert_client_profile(wallet_address)
    _set_ui_session_cookies(response, role=user_role, wallet=wallet_address)

    return {
        "success": True,
        "wallet_address": wallet_address,
        "network": network,
        "managed_wallet": True,
        "role": user_role,
        "next": "/ui/auth?stage=details",
    }


@router.get("/api/auth/google/start")
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
    account = upsert_user_account(
        email=profile.get("email"),
        display_name=profile.get("name"),
        role=role,
        google_sub=profile.get("sub"),
    )

    wallet_record = get_primary_wallet_for_user(str(account.get("id", ""))) if account.get("id") else None
    wallet = (wallet_record or {}).get("wallet_address") or ""
    user_ready = bool(account.get("email") and account.get("display_name"))
    client_ready = True if role == "merchant" else bool(wallet and get_client_profile(wallet))
    redirect = "/ui/auth?stage=details" if not (user_ready and client_ready) else _role_dashboard_path(role)
    response = RedirectResponse(url=redirect, status_code=303)
    _set_ui_session_cookies(response, role=role, wallet=wallet)
    return response


@router.get("/api/auth/onboarding-status")
async def ui_onboarding_status(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return {
            "authenticated": False,
            "requires_details": False,
            "role": None,
            "wallet": None,
            "redirect": "/ui/auth",
        }

    role = str(session.get("role") or "client").strip().lower()
    wallet = str(session.get("wallet") or "").strip()

    user = get_user_account_by_wallet(wallet) if wallet else None
    has_user_profile = bool(user and user.get("email") and user.get("display_name"))
    has_client_profile = bool(wallet and get_client_profile(wallet)) if role == "client" else True
    requires_details = not has_user_profile or not has_client_profile

    return {
        "authenticated": True,
        "role": role,
        "wallet": wallet,
        "has_user_profile": has_user_profile,
        "has_client_profile": has_client_profile,
        "requires_details": requires_details,
        "redirect": "/ui/auth?stage=details" if requires_details else _role_dashboard_path(role),
    }


@router.post("/api/auth/register")
async def ui_register(payload: Dict[str, Any], request: Request, response: Response):
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authenticate first using wallet or Google sign-in")

    email = str(payload.get("email", "")).strip().lower()
    display_name = str(payload.get("display_name", "")).strip()
    role = str(payload.get("role") or session.get("role") or "client").strip().lower()
    wallet = str(payload.get("wallet_address") or session.get("wallet") or "").strip()

    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")
    if not display_name:
        raise HTTPException(status_code=400, detail="display_name is required")
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")

    account = upsert_user_account(
        email=email,
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
                user_id=account.get("id"),
                is_primary=True,
                managed_wallet=False,
            )
        if account.get("id"):
            assign_wallet_to_user(wallet, str(account.get("id")))
        if role == "client":
            upsert_client_profile(wallet)

    _set_ui_session_cookies(response, role=role, wallet=wallet or "")
    return {
        "success": True,
        "account": account,
        "wallet": wallet or None,
        "redirect": _role_dashboard_path(role),
    }


@router.post("/api/auth/session-role")
async def ui_set_session_role(payload: Dict[str, Any], request: Request, response: Response):
    session = get_ui_session_from_request(request)
    if not session:
        raise HTTPException(status_code=401, detail="Authentication required")

    role = str(payload.get("role", "client")).strip().lower()
    if role not in {"client", "merchant"}:
        raise HTTPException(status_code=400, detail="role must be either 'client' or 'merchant'")
    wallet = session.get("wallet")
    _set_ui_session_cookies(response, role=role, wallet=wallet)
    return {"success": True, "role": role}


@router.post("/api/auth/session/start")
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
    if not get_wallet_record(wallet):
        raise HTTPException(status_code=403, detail="Wallet not registered. Connect or create wallet first.")
    _set_ui_session_cookies(response, role=role, wallet=wallet)
    onboarding = {
        "has_user_profile": False,
        "has_client_profile": False,
        "requires_details": True,
    }
    user = get_user_account_by_wallet(wallet)
    if user:
        onboarding["has_user_profile"] = bool(user.get("email") and user.get("display_name"))
    if role == "merchant":
        onboarding["has_client_profile"] = True
    else:
        onboarding["has_client_profile"] = bool(get_client_profile(wallet))
    onboarding["requires_details"] = not (onboarding["has_user_profile"] and onboarding["has_client_profile"])
    redirect = "/ui/auth?stage=details" if onboarding["requires_details"] else _role_dashboard_path(role)
    return {
        "success": True,
        "role": role,
        "wallet": wallet,
        "redirect": redirect,
        **onboarding,
    }


@router.post("/api/auth/logout")
async def ui_logout(response: Response):
    response.delete_cookie(UI_SESSION_COOKIE, path="/")
    response.delete_cookie(UI_ROLE_COOKIE, path="/")
    return {"success": True}


@router.get("/api/auth/session")
async def ui_get_session_role(request: Request):
    session = get_ui_session_from_request(request)
    if not session:
        return {"authenticated": False, "role": None, "wallet": None}
    return {
        "authenticated": True,
        "role": session.get("role"),
        "wallet": session.get("wallet"),
        "expires_at": session.get("exp"),
    }


@router.post("/api/auth/login")
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
            wallet_record = get_primary_wallet_for_user(str(user.get("id", ""))) if user.get("id") else None
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

    _set_ui_session_cookies(response, role=resolved_role, wallet=wallet)
    return {
        "success": True,
        "role": resolved_role,
        "wallet": wallet,
        "redirect": _role_dashboard_path(resolved_role),
    }


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
