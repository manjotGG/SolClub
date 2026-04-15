import json
import os
import sqlite3
from pathlib import Path

from database.db_manager import DBManager


ROOT = Path(__file__).resolve().parents[1]
SQLITE_PATH = ROOT / "solclub.db"
DATA_DIR = ROOT / "data"


def _safe_json(path: Path):
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    return json.loads(text)


def migrate_sqlite(dbm: DBManager):
    if not SQLITE_PATH.exists():
        print("SQLite database not found, skipping sqlite migration.")
        return

    conn = sqlite3.connect(SQLITE_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    try:
        cur.execute("SELECT id, name, wallet_address, api_key, created_at FROM merchants")
        for row in cur.fetchall():
            dbm.client.table("merchants").upsert(dict(row)).execute()
    except Exception:
        pass

    try:
        cur.execute("SELECT id, wallet, merchant_id, amount, signature, created_at FROM transactions")
        for row in cur.fetchall():
            payload = dict(row)
            payload["wallet_address"] = payload.pop("wallet")
            dbm.client.table("transactions").upsert(payload, on_conflict="signature").execute()
    except Exception:
        pass

    try:
        cur.execute("SELECT id, wallet, nft_type, mint_address, created_at FROM nft_records")
        for row in cur.fetchall():
            payload = dict(row)
            payload["wallet_address"] = payload.pop("wallet")
            dbm.client.table("nfts").upsert(payload, on_conflict="mint_address").execute()
    except Exception:
        pass

    try:
        cur.execute(
            "SELECT id, wallet, merchant_id, transaction_signature, transaction_amount, cashback_amount, reward_tier, created_at FROM cashback_rewards"
        )
        for row in cur.fetchall():
            payload = dict(row)
            payload["wallet_address"] = payload.pop("wallet")
            payload["cashback_rate"] = (
                float(payload["cashback_amount"]) / float(payload["transaction_amount"])
                if float(payload.get("transaction_amount") or 0) > 0
                else 0
            )
            dbm.client.table("cashback_rewards").upsert(payload, on_conflict="transaction_signature").execute()
    except Exception:
        pass

    try:
        cur.execute(
            "SELECT id, name, cashback_pool_percentage, max_cashback_limit, weekly_distribution_rules FROM merchant_profiles"
        )
        for row in cur.fetchall():
            payload = dict(row)
            rules = payload.get("weekly_distribution_rules")
            if isinstance(rules, str):
                try:
                    payload["weekly_distribution_rules"] = json.loads(rules)
                except Exception:
                    payload["weekly_distribution_rules"] = {}
            dbm.client.table("merchant_profiles").upsert(payload).execute()
    except Exception:
        pass

    conn.close()


def migrate_json(dbm: DBManager):
    records = _safe_json(DATA_DIR / "real_nft_records.json")
    for rec in records:
        payload = {
            "wallet_address": rec.get("owner"),
            "nft_type": rec.get("nft_type") or rec.get("rarity") or "unknown",
            "mint_address": rec.get("mint_address"),
            "metadata_uri": rec.get("metadata_uri"),
            "created_at": rec.get("minted_at"),
        }
        if payload["wallet_address"] and payload["mint_address"]:
            dbm.client.table("nfts").upsert(payload, on_conflict="mint_address").execute()

    users = _safe_json(DATA_DIR / "loyalty_users.json")
    for user in users:
        wallet = user.get("wallet")
        if not wallet:
            continue
        payload = {
            "wallet_address": wallet,
            "joined_date": user.get("joined_date"),
            "loyalty_tier": user.get("loyalty_tier") or "bronze",
            "status": user.get("status") or "active",
        }
        dbm.client.table("client_profiles").upsert(payload, on_conflict="wallet_address").execute()

    requests_meta = _safe_json(DATA_DIR / "transaction_metadata.json")
    for item in requests_meta:
        reference = item.get("reference")
        if not reference:
            continue
        payload = {
            "reference": reference,
            "user_wallet": item.get("user_wallet") or "unknown",
            "store_id": item.get("store_id") or "unknown",
            "status": item.get("status") or "pending",
            "qr_type": item.get("qr_type") or "backend",
            "updated_at": item.get("timestamp"),
        }
        dbm.client.table("payment_requests").upsert(payload, on_conflict="reference").execute()


def main():
    dbm = DBManager()
    if not dbm.is_configured():
        raise RuntimeError("Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY first.")

    print("Starting migration to Supabase...")
    migrate_sqlite(dbm)
    migrate_json(dbm)
    print("Migration completed.")


if __name__ == "__main__":
    main()
