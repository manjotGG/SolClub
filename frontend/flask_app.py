import base64
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlencode

from cryptography.fernet import Fernet
from flask import Flask, jsonify, render_template, request
from solders.keypair import Keypair
from solders.pubkey import Pubkey

from database.db import (
    count_nft_records,
    create_merchant,
    get_merchant_analytics,
    get_merchant_nft_tracking,
    get_merchant_profile,
    list_cashback_rewards,
    list_nft_records,
    list_wallet_transactions,
    save_reward_feedback,
    upsert_client_profile,
    upsert_merchant_profile,
    upsert_wallet_record,
)
from loyalty_engine.loyalty_engine import LoyaltyRulesEngine


def create_app() -> Flask:
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config["JSON_SORT_KEYS"] = False

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/health")
    def api_health():
        return jsonify({"status": "ok", "service": "solclub-frontend", "ts": datetime.now().isoformat()})

    @app.get("/api/client/<wallet>/snapshot")
    def client_snapshot(wallet: str):
        normalized_wallet = wallet.strip()
        merchant_id = int(request.args.get("merchant_id", 1))

        rewards = list_cashback_rewards(normalized_wallet, merchant_id=merchant_id, limit=100)
        txs = list_wallet_transactions(normalized_wallet, limit=200)
        nfts = list_nft_records(normalized_wallet)

        total_spent = round(sum(float(t.get("amount", 0) or 0) for t in txs), 6)
        total_cashback = round(sum(float(r.get("cashback_amount", 0) or 0) for r in rewards), 6)

        engine = LoyaltyRulesEngine(use_sqlite=False)
        tier = engine.calculate_tier(len(txs))
        milestone = engine.get_next_milestone(len(txs))

        return jsonify(
            {
                "wallet": normalized_wallet,
                "merchant_id": merchant_id,
                "total_transactions": len(txs),
                "total_spent": total_spent,
                "total_cashback": total_cashback,
                "nft_count": count_nft_records(normalized_wallet),
                "tier": tier,
                "next_milestone": milestone,
                "recent_transactions": txs[:10],
                "recent_rewards": rewards[:10],
                "recent_nfts": nfts[:10],
            }
        )

    @app.get("/api/client/<wallet>/reward-preview")
    def reward_preview(wallet: str):
        merchant_id = int(request.args.get("merchant_id", 1))
        amount = float(request.args.get("amount", 0.01))
        engine = LoyaltyRulesEngine(use_sqlite=False)
        decision = engine.evaluate_cashback_and_nft(wallet=wallet.strip(), merchant_id=merchant_id, transaction_amount=amount)

        return jsonify(
            {
                "wallet": decision.wallet,
                "merchant_id": decision.merchant_id,
                "weekly_transaction_count": decision.weekly_transaction_count,
                "reward_tier": decision.reward_tier,
                "cashback_rate": decision.cashback_rate,
                "cashback_amount": decision.cashback_amount,
                "nft_rarity": decision.nft_rarity,
            }
        )

    @app.post("/api/client/<wallet>/feedback")
    def reward_feedback(wallet: str):
        payload = request.get_json(silent=True) or {}
        merchant_id = int(payload.get("merchant_id", 1))
        rating = int(payload.get("rating", 5))
        message = payload.get("message")
        save_reward_feedback(wallet.strip(), merchant_id, rating, message)
        return jsonify({"success": True, "wallet": wallet.strip(), "merchant_id": merchant_id})

    @app.get("/api/merchant/<int:merchant_id>/analytics")
    def merchant_analytics(merchant_id: int):
        return jsonify(get_merchant_analytics(merchant_id))

    @app.get("/api/merchant/<int:merchant_id>/nfts")
    def merchant_nfts(merchant_id: int):
        limit = int(request.args.get("limit", 100))
        return jsonify({"merchant_id": merchant_id, "items": get_merchant_nft_tracking(merchant_id, limit=limit)})

    @app.get("/api/merchant/<int:merchant_id>/cashback-config")
    def merchant_cashback_get(merchant_id: int):
        profile = get_merchant_profile(merchant_id)
        if not profile:
            return jsonify({"error": "Merchant profile not found"}), 404
        return jsonify(profile)

    @app.post("/api/merchant/<int:merchant_id>/cashback-config")
    def merchant_cashback_post(merchant_id: int):
        payload = request.get_json(silent=True) or {}
        upsert_merchant_profile(
            merchant_id=merchant_id,
            name=str(payload.get("name", f"merchant-{merchant_id}")),
            cashback_pool_percentage=float(payload.get("cashback_pool_percentage", 2.0)),
            max_cashback_limit=float(payload.get("max_cashback_limit", 0.05)),
            weekly_distribution_rules=payload.get("weekly_distribution_rules", {"base_rate": 0.01, "tiers": []}),
        )
        return jsonify({"success": True, "merchant_id": merchant_id})

    @app.post("/api/merchant/account")
    def merchant_account_create():
        payload = request.get_json(silent=True) or {}
        name = str(payload.get("name", ""))
        wallet_address = str(payload.get("wallet_address", "")).strip()
        if not name or not wallet_address:
            return jsonify({"error": "name and wallet_address are required"}), 400

        api_key = secrets.token_hex(16)
        merchant = create_merchant(name, wallet_address, api_key)
        merchant_id = int(merchant.get("id", 1))
        upsert_merchant_profile(
            merchant_id=merchant_id,
            name=name,
            cashback_pool_percentage=2.0,
            max_cashback_limit=0.05,
            weekly_distribution_rules={"base_rate": 0.01, "tiers": []},
        )
        return jsonify({"success": True, "merchant": merchant, "api_key": api_key})

    @app.post("/api/wallet/connect")
    def wallet_connect():
        payload = request.get_json(silent=True) or {}
        wallet = str(payload.get("wallet_address", "")).strip()
        if not wallet:
            return jsonify({"error": "wallet_address is required"}), 400

        try:
            Pubkey.from_string(wallet)
        except Exception:
            return jsonify({"error": "Invalid Solana wallet address"}), 400

        upsert_wallet_record(
            wallet_address=wallet,
            network=str(payload.get("network", "testnet")),
            provider=payload.get("provider"),
            is_primary=True,
            managed_wallet=False,
        )
        if str(payload.get("user_role", "client")) == "client":
            upsert_client_profile(wallet)

        return jsonify({"success": True, "wallet": wallet})

    @app.post("/api/wallet/auto-create")
    def wallet_auto_create():
        payload = request.get_json(silent=True) or {}
        network = str(payload.get("network", "testnet")).lower()
        if network != "testnet":
            return jsonify({"error": "Managed wallet creation is enabled for testnet only"}), 400

        keypair = Keypair()
        wallet_address = str(keypair.pubkey())
        secret_bytes = bytes(keypair)

        encryption_key = os.getenv("WALLET_ENCRYPTION_KEY", "").strip()
        if not encryption_key:
            return jsonify({"error": "Missing WALLET_ENCRYPTION_KEY in environment"}), 500

        encrypted_secret = Fernet(encryption_key.encode("utf-8")).encrypt(secret_bytes).decode("utf-8")
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

        return jsonify(
            {
                "success": True,
                "wallet_address": wallet_address,
                "network": network,
                "managed_wallet": True,
            }
        )

    @app.get("/api/auth/google/start")
    def google_oauth_start():
        role = request.args.get("role", "client")
        client_id = os.getenv("GOOGLE_CLIENT_ID")
        redirect_uri = os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/platform/auth/google/callback")
        if not client_id:
            return jsonify({"error": "GOOGLE_CLIENT_ID not configured"}), 500

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
        return jsonify({"state": state, "auth_url": f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"})

    return app


app = create_app()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("FLASK_PORT", "5050")), debug=True)
