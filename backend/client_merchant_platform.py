from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from database.db import (
    count_nft_records,
    get_merchant_profile,
    list_cashback_rewards,
    upsert_merchant_profile,
)
from loyalty_engine.loyalty_engine import LoyaltyRulesEngine


router = APIRouter(prefix="/platform", tags=["client-merchant-platform"])


class CashbackPoolRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    cashback_pool_percentage: float = Field(..., gt=0, le=100)
    max_cashback_limit: float = Field(..., gt=0)
    weekly_distribution_rules: Dict[str, Any]


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

    total_cashback = round(sum(item["cashback_amount"] for item in cashback_history), 6)

    return {
        "wallet": normalized_wallet,
        "merchant_id": merchant_id,
        "total_cashback": total_cashback,
        "cashback_events": len(cashback_history),
        "nft_count": nft_count,
        "cashback_history": cashback_history,
    }


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
