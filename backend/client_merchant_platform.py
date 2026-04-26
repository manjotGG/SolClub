import base64
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

import requests
from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solders.signature import Signature
from solana.exceptions import SolanaRpcException
from solana.rpc.async_api import AsyncClient

from database.db import (
    count_nft_records,
    create_franchise,
    create_merchant,
    get_merchant_analytics,
    get_merchant_nft_tracking,
    get_merchant_profile,
    get_wallet_record,
    list_cashback_rewards,
    list_franchises,
    list_nft_records,
    list_reward_feedback,
    list_wallet_transactions,
    mark_wallet_auth_challenge_used,
    save_reward_feedback,
    save_wallet_auth_challenge,
    upsert_client_profile,
    upsert_merchant_profile,
    upsert_user_account,
    upsert_wallet_record,
    get_wallet_auth_challenge,
)
from loyalty_engine.loyalty_engine import LoyaltyRulesEngine

router = APIRouter(prefix="/platform", tags=["client-merchant-platform"])


_google_state_store: Dict[str, float] = {}


class CashbackPoolRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    cashback_pool_percentage: float = Field(..., gt=0, le=100)
    max_cashback_limit: float = Field(..., gt=0)
    weekly_distribution_rules: Dict[str, Any]


class MerchantAccountRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    wallet_address: str = Field(..., min_length=32)
    email: Optional[str] = None


class FranchiseRequest(BaseModel):
    franchise_name: str = Field(..., min_length=2, max_length=120)
    location: Optional[str] = None


class WalletConnectRequest(BaseModel):
    wallet_address: str = Field(..., min_length=32)
    network: str = Field(default="testnet")
    provider: Optional[str] = None
    user_role: str = Field(default="client")


class AutoWalletRequest(BaseModel):
    network: str = Field(default="testnet")
    provider: str = Field(default="solclub-managed")
    created_by: Optional[str] = None


class FundWalletRequest(BaseModel):
    wallet_address: str
    amount_sol: float = Field(default=1.0, gt=0, le=5.0)


class WalletAuthChallengeRequest(BaseModel):
    wallet_address: str


class WalletAuthVerifyRequest(BaseModel):
    wallet_address: str
    nonce: str
    signature: str


class RewardFeedbackRequest(BaseModel):
    merchant_id: int = Field(default=1)
    rating: int = Field(..., ge=1, le=5)
    message: Optional[str] = Field(default=None, max_length=500)


def _app_secret() -> str:
    secret = os.getenv("APP_AUTH_SECRET")
    if secret:
        return secret
    return "dev-insecure-secret-change-in-production"


def _make_app_token(payload: Dict[str, Any]) -> str:
    content = {
        **payload,
        "exp": int((datetime.now(tz=timezone.utc) + timedelta(hours=8)).timestamp()),
        "iat": int(datetime.now(tz=timezone.utc).timestamp()),
    }
    raw = str(content).encode("utf-8") + _app_secret().encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("utf-8")


def _wallet_encryption_key() -> bytes:
    key = os.getenv("WALLET_ENCRYPTION_KEY", "").strip()
    if not key:
        raise RuntimeError("Missing WALLET_ENCRYPTION_KEY in environment.")
    return key.encode("utf-8")


def _encrypt_secret(secret_bytes: bytes) -> str:
    f = Fernet(_wallet_encryption_key())
    return f.encrypt(secret_bytes).decode("utf-8")


def _verify_wallet_signature(wallet_address: str, nonce: str, signature: str) -> bool:
    message = f"SolClub wallet auth:{nonce}".encode("utf-8")
    sig = Signature.from_string(signature)
    pubkey = Pubkey.from_string(wallet_address)
    return bool(sig.verify(pubkey, message))


def _google_redirect_uri() -> str:
    configured = os.getenv("GOOGLE_REDIRECT_URI", "").strip()
    if configured and configured != "http://localhost:8000/platform/auth/google/callback":
        return configured
    return "http://localhost:8000/ui/api/auth/google/callback"


@router.get("/dashboard")
async def platform_dashboard():
        return {
        "message": "Frontend is served by FastAPI UI routes.",
        "ui_url": os.getenv("UI_URL", "http://localhost:8000/ui/client"),
        }


@router.get("/auth/google/start")
async def google_oauth_start(role: str = Query(default="client")):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = _google_redirect_uri()
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

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
    url = f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    return {"auth_url": url, "state": state}


@router.get("/auth/google/callback")
async def google_oauth_callback(code: Optional[str] = None, state: Optional[str] = None):
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_parts = state.split(":")
    state_key = state_parts[0]
    role = state_parts[1] if len(state_parts) > 1 else "client"
    expires_at = _google_state_store.get(state_key)
    if not expires_at or time.time() > expires_at:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    client_id = os.getenv("GOOGLE_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
    redirect_uri = _google_redirect_uri()

    if not client_id or not client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth credentials not configured")

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
    user_res = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=20,
    )
    profile = user_res.json()

    google_email = str(profile.get("email") or "").strip().lower()
    username_hint = str(profile.get("name") or "").strip() or (google_email.split("@")[0] if "@" in google_email else None)
    account = upsert_user_account(
        email=(google_email or None),
        username=username_hint,
        display_name=profile.get("name"),
        role=role,
        google_sub=profile.get("sub"),
    )

    token = _make_app_token(
        {
            "provider": "google",
            "email": profile.get("email"),
            "role": role,
            "user": account.get("id") or profile.get("sub"),
        }
    )

    return {"success": True, "account": account, "token": token}


@router.post("/auth/wallet/challenge")
async def wallet_auth_challenge(payload: WalletAuthChallengeRequest):
    wallet = payload.wallet_address.strip()
    nonce = secrets.token_urlsafe(24)
    expires = (datetime.now(tz=timezone.utc) + timedelta(minutes=10)).isoformat()
    save_wallet_auth_challenge(wallet, nonce, expires)
    message = f"SolClub wallet auth:{nonce}"
    return {"wallet": wallet, "nonce": nonce, "message": message, "expires_at": expires}


@router.post("/auth/wallet/verify")
async def wallet_auth_verify(payload: WalletAuthVerifyRequest):
    wallet = payload.wallet_address.strip()
    challenge = get_wallet_auth_challenge(wallet, payload.nonce)
    if not challenge:
        raise HTTPException(status_code=400, detail="Challenge missing or already used")

    expires_at = challenge.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at.replace("Z", "+00:00")) < datetime.now(tz=timezone.utc):
        raise HTTPException(status_code=400, detail="Challenge expired")

    try:
        verified = _verify_wallet_signature(wallet, payload.nonce, payload.signature)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Signature verification failed: {exc}")

    if not verified:
        raise HTTPException(status_code=401, detail="Invalid wallet signature")

    mark_wallet_auth_challenge_used(wallet, payload.nonce)
    upsert_client_profile(wallet)
    token = _make_app_token({"provider": "wallet", "wallet": wallet, "role": "client"})
    return {"success": True, "wallet": wallet, "token": token}


@router.post("/wallet/connect")
async def wallet_connect(payload: WalletConnectRequest):
    wallet = payload.wallet_address.strip()
    try:
        Pubkey.from_string(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Solana wallet address")

    upsert_wallet_record(
        wallet_address=wallet,
        network=payload.network,
        provider=payload.provider,
        is_primary=True,
        managed_wallet=False,
    )
    if payload.user_role == "client":
        upsert_client_profile(wallet)

    return {"success": True, "wallet": wallet, "network": payload.network, "managed_wallet": False}


@router.post("/wallet/auto-create")
async def wallet_auto_create(payload: AutoWalletRequest):
    if payload.network.lower() != "testnet":
        raise HTTPException(status_code=400, detail="Managed wallet creation is currently enabled for testnet only")

    keypair = Keypair()
    wallet_address = str(keypair.pubkey())
    secret_bytes = bytes(keypair)

    try:
        encrypted_secret = _encrypt_secret(secret_bytes)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Secure key management setup missing: {exc}")

    upsert_wallet_record(
        wallet_address=wallet_address,
        network=payload.network,
        provider=payload.provider,
        is_primary=True,
        managed_wallet=True,
        encrypted_secret=encrypted_secret,
        created_by=payload.created_by,
    )
    upsert_client_profile(wallet_address)

    return {
        "success": True,
        "wallet_address": wallet_address,
        "network": payload.network,
        "managed_wallet": True,
        "warning": "Private key is encrypted in DB. Keep WALLET_ENCRYPTION_KEY secure.",
    }


@router.post("/wallet/fund-testnet")
async def wallet_fund_testnet(payload: FundWalletRequest):
    wallet = payload.wallet_address.strip()
    try:
        pubkey = Pubkey.from_string(wallet)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid wallet")

    client = AsyncClient(os.getenv("SOLANA_AIRDROP_RPC_URL", os.getenv("SOLANA_RPC_URL", "https://api.testnet.solana.com")))
    try:
        sig = await client.request_airdrop(pubkey, int(payload.amount_sol * 1_000_000_000))
        return {
            "success": True,
            "wallet": wallet,
            "amount_sol": payload.amount_sol,
            "airdrop_signature": str(sig.value) if sig and sig.value else None,
        }
    except SolanaRpcException as exc:
        detail = str(exc)
        if "429" in detail or "Too Many Requests" in detail:
            raise HTTPException(
                status_code=503,
                detail="Solana testnet faucet is rate-limited right now. Please retry in a minute.",
            )
        raise HTTPException(
            status_code=502,
            detail="Solana RPC could not process the airdrop request. Please retry shortly.",
        )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Unexpected RPC error while funding wallet: {exc}")
    finally:
        await client.close()


@router.post("/merchant/account-creation")
async def merchant_account_creation(payload: MerchantAccountRequest):
    api_key = secrets.token_hex(16)
    merchant = create_merchant(payload.name, payload.wallet_address, api_key)
    merchant_id = int(merchant.get("id", 1))
    upsert_merchant_profile(
        merchant_id=merchant_id,
        name=payload.name,
        cashback_pool_percentage=2.0,
        max_cashback_limit=0.05,
        weekly_distribution_rules={
            "base_rate": 0.01,
            "tiers": [
                {"min_transactions": 3, "rate": 0.02},
                {"min_transactions": 5, "rate": 0.03},
                {"min_transactions": 10, "rate": 0.05},
            ],
        },
    )
    merchant_username = re.sub(r"[^a-zA-Z0-9_]", "_", str(payload.name or "merchant")).strip("_")[:32] or "merchant"
    upsert_user_account(email=payload.email, username=merchant_username, display_name=payload.name, role="merchant")
    return {"success": True, "merchant": merchant, "api_key": api_key}


@router.post("/merchant/{merchant_id}/franchise-registration")
async def merchant_franchise_registration(merchant_id: int, payload: FranchiseRequest):
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    franchise = create_franchise(merchant_id, payload.franchise_name, payload.location)
    return {"success": True, "franchise": franchise}


@router.get("/merchant/{merchant_id}/franchises")
async def merchant_franchises(merchant_id: int):
    return {"merchant_id": merchant_id, "franchises": list_franchises(merchant_id)}


@router.get("/merchant/{merchant_id}/cashback-pool")
async def get_cashback_pool(merchant_id: int):
    profile = get_merchant_profile(merchant_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Merchant profile not found")
    return profile


@router.post("/merchant/{merchant_id}/cashback-pool")
async def configure_cashback_pool(merchant_id: int, payload: CashbackPoolRequest):
    upsert_merchant_profile(
        merchant_id=merchant_id,
        name=payload.name,
        cashback_pool_percentage=payload.cashback_pool_percentage,
        max_cashback_limit=payload.max_cashback_limit,
        weekly_distribution_rules=payload.weekly_distribution_rules,
    )
    return {
        "success": True,
        "merchant_id": merchant_id,
        "message": "Cashback pool configuration updated",
    }


@router.get("/merchant/{merchant_id}/analytics-dashboard")
async def merchant_analytics_dashboard(merchant_id: int):
    analytics = get_merchant_analytics(merchant_id)
    feedback = list_reward_feedback(merchant_id, limit=20)
    return {"analytics": analytics, "feedback": feedback}


@router.get("/merchant/{merchant_id}/nft-distribution-tracking")
async def merchant_nft_distribution_tracking(merchant_id: int, limit: int = 100):
    return {
        "merchant_id": merchant_id,
        "nft_distribution": get_merchant_nft_tracking(merchant_id, limit=limit),
    }


@router.get("/client/{wallet}/nfts")
async def client_nfts(wallet: str):
    normalized_wallet = wallet.strip()
    nfts = list_nft_records(normalized_wallet)
    return {"wallet": normalized_wallet, "total": len(nfts), "items": nfts}


@router.get("/client/{wallet}/rewards")
async def get_client_rewards(wallet: str, merchant_id: Optional[int] = None):
    normalized_wallet = wallet.strip()
    rows = list_cashback_rewards(normalized_wallet, merchant_id=merchant_id, limit=50)
    nft_count = count_nft_records(normalized_wallet)

    cashback_history: List[Dict[str, Any]] = [
        {
            "transaction_signature": row.get("transaction_signature"),
            "transaction_amount": row.get("transaction_amount"),
            "cashback_amount": row.get("cashback_amount"),
            "reward_tier": row.get("reward_tier"),
            "created_at": row.get("created_at"),
        }
        for row in rows
    ]

    total_cashback = round(sum(float(item["cashback_amount"] or 0) for item in cashback_history), 6)

    return {
        "wallet": normalized_wallet,
        "merchant_id": merchant_id,
        "total_cashback": total_cashback,
        "cashback_events": len(cashback_history),
        "nft_count": nft_count,
        "cashback_history": cashback_history,
    }


@router.get("/client/{wallet}/transactions")
async def client_transactions(wallet: str, limit: int = 50):
    normalized_wallet = wallet.strip()
    txs = list_wallet_transactions(normalized_wallet, limit=limit)
    return {"wallet": normalized_wallet, "count": len(txs), "transactions": txs}


@router.get("/client/{wallet}/loyalty-progress")
async def client_loyalty_progress(wallet: str, merchant_id: int = 1):
    normalized_wallet = wallet.strip()
    txs = list_wallet_transactions(normalized_wallet, limit=500)
    total_transactions = len(txs)
    total_spent = round(sum(float(t.get("amount", 0) or 0) for t in txs), 6)

    engine = LoyaltyRulesEngine(use_sqlite=False)
    tier = engine.calculate_tier(total_transactions)
    milestone = engine.get_next_milestone(total_transactions)
    preview = engine.evaluate_cashback_and_nft(normalized_wallet, merchant_id, transaction_amount=0.01)

    return {
        "wallet": normalized_wallet,
        "tier": tier,
        "total_transactions": total_transactions,
        "total_spent": total_spent,
        "next_milestone": milestone,
        "next_cashback_rate": preview.cashback_rate,
        "next_reward_tier": preview.reward_tier,
    }


@router.post("/client/{wallet}/reward-feedback")
async def client_reward_feedback(wallet: str, payload: RewardFeedbackRequest):
    save_reward_feedback(wallet, payload.merchant_id, payload.rating, payload.message)
    return {"success": True, "wallet": wallet.strip(), "merchant_id": payload.merchant_id}


@router.get("/client/{wallet}/reward-preview")
async def preview_reward(wallet: str, merchant_id: int = 1, amount: float = 0.01):
    engine = LoyaltyRulesEngine(use_sqlite=False)
    decision = engine.evaluate_cashback_and_nft(
        wallet=wallet.strip(),
        merchant_id=merchant_id,
        transaction_amount=amount,
    )
    return {
        "wallet": decision.wallet,
        "merchant_id": decision.merchant_id,
        "weekly_transaction_count": decision.weekly_transaction_count,
        "reward_tier": decision.reward_tier,
        "cashback_rate": decision.cashback_rate,
        "cashback_amount": decision.cashback_amount,
        "nft_rarity": decision.nft_rarity,
    }
