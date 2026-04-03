import asyncio
import json
import os
import secrets
from datetime import datetime
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from database.db import (
    count_nft_records,
    count_wallet_transactions,
    get_merchant_analytics,
    get_merchant_nft_tracking,
    list_cashback_rewards,
    list_nft_records,
    list_wallet_transactions,
    save_reward_feedback,
    upsert_client_profile,
    upsert_wallet_record,
)
from loyalty_engine.loyalty_engine import LoyaltyRulesEngine

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATES_DIR = os.path.join(BASE_DIR, "frontend", "templates")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

router = APIRouter(prefix="/ui", tags=["frontend-ui"])


def _json_sse(data: Dict[str, Any]) -> str:
    return f"data: {json.dumps(data, default=str)}\\n\\n"


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
    return templates.TemplateResponse(request, "client.html", {"request": request})


@router.get("/client", response_class=HTMLResponse)
async def ui_client_page(request: Request):
    return templates.TemplateResponse(request, "client.html", {"request": request})


@router.get("/merchant", response_class=HTMLResponse)
async def ui_merchant_page(request: Request):
    return templates.TemplateResponse(request, "merchant.html", {"request": request})


@router.get("/auth", response_class=HTMLResponse)
async def ui_auth_page(request: Request):
    return templates.TemplateResponse(request, "auth.html", {"request": request})


@router.get("/api/client/{wallet}/snapshot")
async def ui_client_snapshot(wallet: str, merchant_id: int = 1):
    return _client_snapshot(wallet, merchant_id)


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


@router.get("/api/merchant/{merchant_id}/nfts")
async def ui_merchant_nfts(merchant_id: int, limit: int = 100):
    return {"merchant_id": merchant_id, "items": get_merchant_nft_tracking(merchant_id, limit=limit)}


@router.post("/api/wallet/connect")
async def ui_wallet_connect(payload: Dict[str, Any]):
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
    if str(payload.get("user_role", "client")) == "client":
        upsert_client_profile(wallet)

    return {"success": True, "wallet": wallet}


@router.post("/api/wallet/auto-create")
async def ui_wallet_auto_create(payload: Dict[str, Any]):
    network = str(payload.get("network", "testnet")).lower()
    if network != "testnet":
        raise HTTPException(status_code=400, detail="Managed wallet creation is enabled for testnet only")

    keypair = Keypair()
    wallet_address = str(keypair.pubkey())
    secret_bytes = bytes(keypair)

    key = os.getenv("WALLET_ENCRYPTION_KEY", "").strip()
    if not key:
        raise HTTPException(status_code=500, detail="Missing WALLET_ENCRYPTION_KEY in environment")

    encrypted_secret = Fernet(key.encode("utf-8")).encrypt(secret_bytes).decode("utf-8")
    upsert_wallet_record(
        wallet_address=wallet_address,
        network=network,
        provider=str(payload.get("provider", "solclub-managed")),
        is_primary=True,
        managed_wallet=True,
        encrypted_secret=encrypted_secret,
        created_by=payload.get("created_by"),
    )
    upsert_client_profile(wallet_address)

    return {
        "success": True,
        "wallet_address": wallet_address,
        "network": network,
        "managed_wallet": True,
    }


@router.get("/api/auth/google/start")
async def ui_google_start(role: str = Query(default="client")):
    client_id = os.getenv("GOOGLE_CLIENT_ID")
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/platform/auth/google/callback")
    if not client_id:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID not configured")

    state = secrets.token_urlsafe(24)
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
