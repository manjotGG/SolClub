import os
import json
import base64
import hashlib
import hmac
import secrets
from datetime import datetime
from typing import Any, Dict, List, Optional

from database.db_manager import DBManager

_db = DBManager()


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _hash_password(password: str, salt: Optional[str] = None) -> Dict[str, str]:
    password_salt = salt or secrets.token_hex(16)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        password_salt.encode("utf-8"),
        390000,
    )
    return {
        "password_hash": base64.urlsafe_b64encode(derived).decode("utf-8"),
        "password_salt": password_salt,
    }


def _verify_password(password: str, password_hash: Optional[str], password_salt: Optional[str]) -> bool:
    if not password_hash or not password_salt:
        return False
    candidate = _hash_password(password, password_salt)["password_hash"]
    return hmac.compare_digest(candidate, password_hash)


def init_db() -> bool:
    """Supabase migration note: schema is managed in database/supabase_schema.sql."""
    health = _db.health_check()
    return health.get("status") in {"ok", "not_configured"}


def _require_data(result: Any) -> List[Dict[str, Any]]:
    data = getattr(result, "data", None)
    return data if isinstance(data, list) else []


def _require_client():
    if not _db.is_configured():
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY.")


def get_connection():
    raise RuntimeError("SQLite connections are removed. Use database helper functions backed by Supabase.")


def transaction_exists(signature: str) -> bool:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("id")
        .eq("signature", signature)
        .limit(1)
        .execute()
    )
    return len(_require_data(result)) > 0


def insert_transaction(wallet: str, merchant_id: int, amount: float, signature: str) -> Optional[Dict[str, Any]]:
    _require_client()
    payload = {
        "wallet_address": wallet.strip(),
        "merchant_id": int(merchant_id),
        "amount": float(amount),
        "signature": signature,
        "network": os.getenv("SOLANA_NETWORK", "testnet"),
        "created_at": _now_iso(),
    }
    result = _db.client.table("transactions").insert(payload).execute()
    rows = _require_data(result)
    return rows[0] if rows else None


def list_wallet_transactions(wallet: str, limit: int = 100) -> List[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("*")
        .eq("wallet_address", wallet.strip())
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return _require_data(result)


def count_wallet_transactions(wallet: str) -> int:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("id", count="exact")
        .eq("wallet_address", wallet.strip())
        .execute()
    )
    return int(getattr(result, "count", 0) or 0)


def count_wallet_transactions_since(wallet: str, since_iso: str) -> int:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("id", count="exact")
        .eq("wallet_address", wallet.strip())
        .gte("created_at", since_iso)
        .execute()
    )
    return int(getattr(result, "count", 0) or 0)


def get_merchant_revenue_since(merchant_id: int, since_iso: str) -> float:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("amount")
        .eq("merchant_id", int(merchant_id))
        .gte("created_at", since_iso)
        .execute()
    )
    rows = _require_data(result)
    return float(sum(float(r.get("amount", 0) or 0) for r in rows))


def get_merchant_profile(merchant_id: int):
    _require_client()
    result = (
        _db.client.table("merchant_profiles")
        .select("id,name,cashback_pool_percentage,max_cashback_limit,weekly_distribution_rules")
        .eq("id", int(merchant_id))
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    if not rows:
        return None
    row = rows[0]
    rules = row.get("weekly_distribution_rules") or {}
    if isinstance(rules, str):
        try:
            rules = json.loads(rules)
        except Exception:
            rules = {}
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "cashback_pool_percentage": float(row.get("cashback_pool_percentage", 2.0) or 2.0),
        "max_cashback_limit": float(row.get("max_cashback_limit", 0.05) or 0.05),
        "weekly_distribution_rules": rules,
    }


def upsert_merchant_profile(
    merchant_id: int,
    name: str,
    cashback_pool_percentage: float,
    max_cashback_limit: float,
    weekly_distribution_rules: dict,
):
    _require_client()
    payload = {
        "id": int(merchant_id),
        "name": name,
        "cashback_pool_percentage": float(cashback_pool_percentage),
        "max_cashback_limit": float(max_cashback_limit),
        "weekly_distribution_rules": weekly_distribution_rules,
    }
    _db.client.table("merchant_profiles").upsert(payload).execute()


def save_cashback_reward(
    wallet: str,
    merchant_id: int,
    transaction_signature: str,
    transaction_amount: float,
    cashback_amount: float,
    reward_tier: str,
):
    _require_client()
    tx_res = (
        _db.client.table("transactions")
        .select("id")
        .eq("signature", transaction_signature)
        .limit(1)
        .execute()
    )
    tx_rows = _require_data(tx_res)
    transaction_id = tx_rows[0].get("id") if tx_rows else None

    payload = {
        "wallet_address": wallet.strip(),
        "merchant_id": int(merchant_id),
        "transaction_signature": transaction_signature,
        "transaction_amount": float(transaction_amount),
        "cashback_amount": float(cashback_amount),
        "cashback_rate": float(cashback_amount / transaction_amount) if transaction_amount else 0.0,
        "reward_tier": reward_tier,
        "transaction_id": transaction_id,
        "created_at": _now_iso(),
    }
    _db.client.table("cashback_rewards").upsert(payload, on_conflict="transaction_signature").execute()


def list_cashback_rewards(wallet: str, merchant_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
    _require_client()
    query = (
        _db.client.table("cashback_rewards")
        .select("transaction_signature,transaction_amount,cashback_amount,reward_tier,created_at")
        .eq("wallet_address", wallet.strip())
        .order("created_at", desc=True)
        .limit(limit)
    )
    if merchant_id is not None:
        query = query.eq("merchant_id", int(merchant_id))
    return _require_data(query.execute())


def insert_nft_record(wallet: str, nft_type: str, mint_address: str, metadata_uri: Optional[str] = None):
    _require_client()
    payload = {
        "wallet_address": wallet.strip(),
        "nft_type": nft_type,
        "mint_address": mint_address,
        "metadata_uri": metadata_uri,
        "created_at": _now_iso(),
    }
    _db.client.table("nfts").upsert(payload, on_conflict="mint_address").execute()


def list_nft_records(wallet: str) -> List[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("nfts")
        .select("wallet_address,nft_type,mint_address,metadata_uri,created_at")
        .eq("wallet_address", wallet.strip())
        .order("created_at", desc=True)
        .execute()
    )
    rows = _require_data(result)
    return [
        {
            "owner": r.get("wallet_address"),
            "nft_type": r.get("nft_type"),
            "mint_address": r.get("mint_address"),
            "metadata_uri": r.get("metadata_uri"),
            "minted_at": r.get("created_at"),
            "mystery_revealed": False,
        }
        for r in rows
    ]


def count_nft_records(wallet: str) -> int:
    _require_client()
    result = (
        _db.client.table("nfts")
        .select("id", count="exact")
        .eq("wallet_address", wallet.strip())
        .execute()
    )
    return int(getattr(result, "count", 0) or 0)


def upsert_client_profile(wallet: str, joined_date: Optional[str] = None, loyalty_tier: str = "bronze"):
    _require_client()
    payload = {
        "wallet_address": wallet.strip(),
        "joined_date": joined_date or _now_iso(),
        "loyalty_tier": loyalty_tier,
        "status": "active",
    }
    _db.client.table("client_profiles").upsert(payload, on_conflict="wallet_address").execute()


def get_client_profile(wallet: str) -> Optional[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("client_profiles")
        .select("*")
        .eq("wallet_address", wallet.strip())
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    return rows[0] if rows else None


def save_payment_request(reference: str, user_wallet: str, store_id: str, status: str, qr_type: str, amount: Optional[float] = None):
    _require_client()
    payload = {
        "reference": reference,
        "user_wallet": user_wallet.strip(),
        "store_id": store_id,
        "status": status,
        "qr_type": qr_type,
        "amount": amount,
        "updated_at": _now_iso(),
    }
    _db.client.table("payment_requests").upsert(payload, on_conflict="reference").execute()


def create_merchant(name: str, wallet_address: str, api_key: str) -> Dict[str, Any]:
    _require_client()
    payload = {
        "name": name,
        "wallet_address": wallet_address,
        "api_key": api_key,
        "created_at": _now_iso(),
    }
    result = _db.client.table("merchants").insert(payload).execute()
    rows = _require_data(result)
    return rows[0] if rows else payload


def get_merchant_by_id(merchant_id: int) -> Optional[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("merchants")
        .select("id,name,wallet_address,api_key,created_at")
        .eq("id", int(merchant_id))
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    return rows[0] if rows else None


def get_merchant_by_name(name: str) -> Optional[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("merchants")
        .select("id,name,wallet_address,api_key,created_at")
        .eq("name", name)
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    return rows[0] if rows else None


def get_platform_stats() -> Dict[str, Any]:
    _require_client()
    tx_res = _db.client.table("transactions").select("id,wallet_address").execute()
    tx_rows = _require_data(tx_res)

    cb_res = _db.client.table("cashback_rewards").select("reward_tier").execute()
    cb_rows = _require_data(cb_res)

    nfts_res = _db.client.table("nfts").select("nft_type").execute()
    nft_rows = _require_data(nfts_res)

    unique_wallets = len({r.get("wallet_address") for r in tx_rows if r.get("wallet_address")})

    reward_breakdown: Dict[str, int] = {}
    for row in cb_rows:
        key = row.get("reward_tier") or "unknown"
        reward_breakdown[key] = reward_breakdown.get(key, 0) + 1

    nft_breakdown: Dict[str, int] = {}
    for row in nft_rows:
        key = row.get("nft_type") or "unknown"
        nft_breakdown[key] = nft_breakdown.get(key, 0) + 1

    return {
        "total_users": unique_wallets,
        "total_transactions": len(tx_rows),
        "total_rewards": len(cb_rows),
        "reward_breakdown": reward_breakdown,
        "nft_breakdown": nft_breakdown,
    }


def get_recent_wallet_activity(limit: int = 10) -> List[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("transactions")
        .select("wallet_address,created_at")
        .order("created_at", desc=True)
        .limit(max(1, limit * 5))
        .execute()
    )
    rows = _require_data(result)
    stats: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        wallet = row.get("wallet_address")
        if not wallet:
            continue
        if wallet not in stats:
            stats[wallet] = {
                "wallet": wallet,
                "transactions": 0,
                "last_activity": row.get("created_at"),
            }
        stats[wallet]["transactions"] += 1
    ordered = sorted(stats.values(), key=lambda x: x.get("last_activity") or "", reverse=True)
    return ordered[:limit]


def get_recent_cashback_events(limit: int = 10) -> List[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("cashback_rewards")
        .select("wallet_address,reward_tier,cashback_amount,created_at")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    rows = _require_data(result)
    return [
        {
            "wallet": r.get("wallet_address"),
            "reward_name": r.get("reward_tier"),
            "reward_type": "cashback",
            "earned_at": r.get("created_at"),
            "cashback_amount": r.get("cashback_amount"),
        }
        for r in rows
    ]


def upsert_user_account(
    email: Optional[str],
    display_name: Optional[str],
    role: str,
    google_sub: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    _require_client()
    password_payload: Dict[str, Optional[str]] = {}
    if password:
        password_payload = _hash_password(password)
    payload_candidates = [
        {
            "email": email,
            "display_name": display_name,
            "role": role,
            "google_sub": google_sub,
            **password_payload,
            "updated_at": _now_iso(),
        },
        {
            "email": email,
            "display_name": display_name,
            "role": role,
            **password_payload,
            "updated_at": _now_iso(),
        },
        {
            "email": email,
            "display_name": display_name,
            "role": role,
        },
        {
            "email": email,
            "role": role,
        },
    ]

    last_exc: Optional[Exception] = None
    for payload in payload_candidates:
        try:
            result = _db.client.table("users").upsert(payload, on_conflict="email").execute()
            rows = _require_data(result)
            return rows[0] if rows else payload
        except Exception as exc:
            last_exc = exc
            continue

    raise last_exc or RuntimeError("Failed to upsert user account")


def get_user_account_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("users")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    return rows[0] if rows else None


def get_user_account_by_wallet(wallet_address: str) -> Optional[Dict[str, Any]]:
    _require_client()
    wallet = get_wallet_record(wallet_address)
    user_id = (wallet or {}).get("user_id")
    if not user_id:
        return None
    return get_user_account_by_id(str(user_id))


def get_user_account_by_identifier(identifier: str) -> Optional[Dict[str, Any]]:
    _require_client()
    value = identifier.strip()
    if not value:
        return None

    if "@" in value:
        result = _db.client.table("users").select("*").eq("email", value).limit(1).execute()
        rows = _require_data(result)
        return rows[0] if rows else None

    result = _db.client.table("users").select("*").eq("display_name", value).limit(1).execute()
    rows = _require_data(result)
    return rows[0] if rows else None


def verify_user_password(user: Dict[str, Any], password: str) -> bool:
    return _verify_password(password, user.get("password_hash"), user.get("password_salt"))


def upsert_wallet_record(
    wallet_address: str,
    network: str,
    provider: Optional[str],
    user_id: Optional[str] = None,
    is_primary: bool = True,
    managed_wallet: bool = False,
    encrypted_secret: Optional[str] = None,
    created_by: Optional[str] = None,
):
    _require_client()
    payload = {
        "wallet_address": wallet_address.strip(),
        "network": network,
        "provider": provider,
        "user_id": user_id,
        "is_primary": bool(is_primary),
        "managed_wallet": bool(managed_wallet),
        "encrypted_secret": encrypted_secret,
        "created_by": created_by,
    }
    try:
        _db.client.table("wallets").upsert(payload, on_conflict="wallet_address").execute()
        return
    except Exception:
        # Backward compatibility for environments where new columns are not yet migrated.
        fallback_payload = {
            "wallet_address": wallet_address.strip(),
            "network": network,
            "provider": provider,
            "is_primary": bool(is_primary),
        }
        _db.client.table("wallets").upsert(fallback_payload, on_conflict="wallet_address").execute()


def assign_wallet_to_user(wallet_address: str, user_id: str):
    _require_client()
    try:
        _db.client.table("wallets").update({"user_id": user_id}).eq(
            "wallet_address", wallet_address.strip()
        ).execute()
    except Exception:
        # Allow compatibility with environments where wallets.user_id has not been migrated yet.
        return


def get_primary_wallet_for_user(user_id: str) -> Optional[Dict[str, Any]]:
    _require_client()
    try:
        result = (
            _db.client.table("wallets")
            .select("*")
            .eq("user_id", user_id)
            .order("is_primary", desc=True)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        rows = _require_data(result)
        return rows[0] if rows else None
    except Exception:
        return None


def get_wallet_record(wallet_address: str) -> Optional[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("wallets")
        .select("*")
        .eq("wallet_address", wallet_address.strip())
        .limit(1)
        .execute()
    )
    rows = _require_data(result)
    return rows[0] if rows else None


def save_wallet_auth_challenge(wallet_address: str, nonce: str, expires_at_iso: str):
    _require_client()
    payload = {
        "wallet_address": wallet_address.strip(),
        "nonce": nonce,
        "expires_at": expires_at_iso,
        "used": False,
        "created_at": _now_iso(),
    }
    try:
        _db.client.table("auth_challenges").upsert(payload, on_conflict="wallet_address,nonce").execute()
    except Exception:
        # Allow platform module to run even before schema migration is applied.
        return


def get_wallet_auth_challenge(wallet_address: str, nonce: str) -> Optional[Dict[str, Any]]:
    _require_client()
    try:
        result = (
            _db.client.table("auth_challenges")
            .select("*")
            .eq("wallet_address", wallet_address.strip())
            .eq("nonce", nonce)
            .eq("used", False)
            .limit(1)
            .execute()
        )
        rows = _require_data(result)
        return rows[0] if rows else None
    except Exception:
        return None


def mark_wallet_auth_challenge_used(wallet_address: str, nonce: str):
    _require_client()
    try:
        _db.client.table("auth_challenges").update({"used": True, "used_at": _now_iso()}).eq(
            "wallet_address", wallet_address.strip()
        ).eq("nonce", nonce).execute()
    except Exception:
        return


def create_franchise(merchant_id: int, franchise_name: str, location: Optional[str]) -> Dict[str, Any]:
    _require_client()
    payload = {
        "merchant_id": int(merchant_id),
        "franchise_name": franchise_name,
        "location": location,
        "created_at": _now_iso(),
    }
    result = _db.client.table("franchises").insert(payload).execute()
    rows = _require_data(result)
    return rows[0] if rows else payload


def list_franchises(merchant_id: int) -> List[Dict[str, Any]]:
    _require_client()
    result = (
        _db.client.table("franchises")
        .select("*")
        .eq("merchant_id", int(merchant_id))
        .order("created_at", desc=True)
        .execute()
    )
    return _require_data(result)


def get_merchant_analytics(merchant_id: int) -> Dict[str, Any]:
    _require_client()
    tx_res = (
        _db.client.table("transactions")
        .select("wallet_address,amount,created_at")
        .eq("merchant_id", int(merchant_id))
        .execute()
    )
    tx_rows = _require_data(tx_res)

    cb_res = (
        _db.client.table("cashback_rewards")
        .select("cashback_amount,reward_tier")
        .eq("merchant_id", int(merchant_id))
        .execute()
    )
    cb_rows = _require_data(cb_res)

    unique_clients = len({r.get("wallet_address") for r in tx_rows if r.get("wallet_address")})
    tx_volume = float(sum(float(r.get("amount", 0) or 0) for r in tx_rows))
    cashback_volume = float(sum(float(r.get("cashback_amount", 0) or 0) for r in cb_rows))

    tier_dist: Dict[str, int] = {}
    for row in cb_rows:
        tier = row.get("reward_tier") or "unknown"
        tier_dist[tier] = tier_dist.get(tier, 0) + 1

    return {
        "merchant_id": int(merchant_id),
        "unique_clients": unique_clients,
        "transactions_count": len(tx_rows),
        "transaction_volume": round(tx_volume, 6),
        "cashback_volume": round(cashback_volume, 6),
        "reward_tier_distribution": tier_dist,
    }


def get_merchant_nft_tracking(merchant_id: int, limit: int = 100) -> List[Dict[str, Any]]:
    _require_client()
    tx_res = (
        _db.client.table("transactions")
        .select("wallet_address,signature,created_at")
        .eq("merchant_id", int(merchant_id))
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    tx_rows = _require_data(tx_res)
    wallets = {r.get("wallet_address") for r in tx_rows if r.get("wallet_address")}

    if not wallets:
        return []

    nft_res = _db.client.table("nfts").select("wallet_address,nft_type,mint_address,created_at").execute()
    all_nfts = _require_data(nft_res)
    return [n for n in all_nfts if n.get("wallet_address") in wallets][:limit]


def save_reward_feedback(wallet: str, merchant_id: int, rating: int, message: Optional[str]):
    _require_client()
    payload = {
        "wallet_address": wallet.strip(),
        "merchant_id": int(merchant_id),
        "rating": int(rating),
        "message": message,
        "created_at": _now_iso(),
    }
    try:
        _db.client.table("reward_feedback").insert(payload).execute()
    except Exception:
        return


def list_reward_feedback(merchant_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    _require_client()
    try:
        result = (
            _db.client.table("reward_feedback")
            .select("wallet_address,rating,message,created_at")
            .eq("merchant_id", int(merchant_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return _require_data(result)
    except Exception:
        return []
