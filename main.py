#!/usr/bin/env python3
"""
SolClub - Real Solana Loyalty Program
=====================================

Production entry point for the complete Solana-based loyalty system.
Handles real blockchain transactions, wallet integrations, and NFT rewards.

Features:
- Real Solana Pay QR code generation
- Actual blockchain transaction validation
- Mystery NFT minting with rarity system
- Seasonal NFT collections
- Multi-tier loyalty rewards
- Mobile wallet integration

Usage:
    python main.py [command]

Commands:
    demo     - Run comprehensive demonstration
    server   - Start production API server
    qr       - Generate Solana Pay QR codes
    mint     - Mint mystery NFTs
    help     - Show this help message

Author: SolClub Team
Version: 2.0.0 (Production)
"""
from database.db import init_db
init_db()
import sys
import asyncio
import argparse
import os
from typing import Optional

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(os.path.join(BASE_DIR, "data"))
NFT_RECORDS_FILE = os.path.join(DATA_DIR, "real_nft_records.json")

os.makedirs(DATA_DIR, exist_ok=True)

def show_banner():
    """Display the SolClub banner"""
    print("""
🎯 SolClub - Real Solana Loyalty Program
========================================
✅ Real blockchain transactions (devnet)
✅ Real wallet integrations 
✅ Real NFT minting with metadata
✅ Mystery NFT system with reveals
✅ Seasonal collections
✅ Production-ready API
========================================
    """)

def show_help():
    """Show help information"""
    print(__doc__)

async def run_demo():
    """Run the comprehensive demo"""
    print("🚀 Starting comprehensive demo...")
    try:
        # Import and run the real demo
        from demo import demo_solana_loyalty
        await demo_solana_loyalty()
    except ImportError as e:
        print(f"❌ Demo not available: {e}")
        print("Make sure real_demo.py is in the current directory")
    except Exception as e:
        print(f"❌ Demo failed: {e}")

def start_server():
    """Start the production API server"""
    print("🌐 Starting production API server...")
    try:
        import uvicorn
        
        print("📱 Ready for mobile wallet connections!")
        print("🔗 API Documentation: http://localhost:8000/docs")
        print("✨ This backend handles Solana transactions!")
        print("🖥️ UI Pages: http://localhost:8000/ui/client")
        
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
    except ImportError as e:
        print(f"❌ Server not available: {e}")
        print("Install dependencies: pip install fastapi uvicorn")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")

def create_fastapi_app():
    """Create and configure the FastAPI application with full blockchain integration"""
    from fastapi import FastAPI, HTTPException, Query, Request
    from fastapi.responses import JSONResponse, RedirectResponse
    from fastapi.staticfiles import StaticFiles
    from fastapi.middleware.gzip import GZipMiddleware
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.middleware.trustedhost import TrustedHostMiddleware
    from fastapi.middleware.httpsredirect import HTTPSRedirectMiddleware
    from contextlib import asynccontextmanager
    from pydantic import BaseModel
    from typing import Optional, Dict, Any, List
    import json
    import os
    import uuid
    from database.db import (
        count_wallet_transactions,
        create_merchant,
        get_client_profile,
        get_platform_stats,
        get_merchant_by_id as db_get_merchant_by_id,
        get_merchant_by_name as db_get_merchant_by_name,
        insert_transaction,
        list_nft_records,
        list_wallet_transactions,
        save_cashback_reward,
        save_payment_request,
        transaction_exists,
        upsert_client_profile,
    )
    import asyncio
    from datetime import datetime, timedelta
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Commitment
    from solders.pubkey import Pubkey
    from solders.signature import Signature
    from solders.keypair import Keypair
    from nft_minting.nft_minter import mint_nft
    from loyalty_engine.loyalty_engine import LoyaltyRulesEngine
    
    # Pydantic models
    class ValidationRequest(BaseModel):
        signature: str
        wallet: str
        amount: Optional[float] = None
        merchant_id: Optional[int] = None

    class WalletConnectRequest(BaseModel):
        publicKey: str
        signature: Optional[str] = None
        message: Optional[str] = None
    
    class TransactionValidation(BaseModel):
        signature: str
        reference: str
        amount: Optional[float] = None
    
    class SolanaPayRequest(BaseModel):
        recipient: str
        amount: float
        reference: str
        label: str
        message: str
        store_id: str
    
    # Solana client setup
    # Transactions are on testnet; use testnet endpoint for validation
    SOLANA_CLIENT = AsyncClient("https://api.testnet.solana.com")
    COMMITMENT = Commitment("confirmed")
    
    # Load merchant keypair
    def load_merchant_keypair():
        keypair_path = os.path.join(DATA_DIR, "merchant_keypair.json")
        if os.path.exists(keypair_path):
            with open(keypair_path, 'r') as f:
                keypair_data = json.load(f)
                return Keypair.from_bytes(bytes(keypair_data))
        else:
            # Create new merchant keypair if not exists
            keypair = Keypair()
            os.makedirs(os.path.dirname(keypair_path), exist_ok=True)
            with open(keypair_path, 'w') as f:
                json.dump(list(bytes(keypair)), f)
            print(f"🔑 Created new merchant wallet: {keypair.pubkey()}")
            return keypair
    
    try:
        MERCHANT_KEYPAIR = load_merchant_keypair()
        MERCHANT_WALLET = MERCHANT_KEYPAIR.pubkey()
    except Exception as e:
        print(f"⚠️ Warning: Could not load merchant keypair: {e}")
        MERCHANT_WALLET = None
    
    # Utility functions
    def save_transaction_data(transactions: List[Dict]):
        """Persist transaction request metadata to Supabase."""
        try:
            for tx in transactions:
                if not tx.get("reference"):
                    continue
                save_payment_request(
                    reference=tx.get("reference"),
                    user_wallet=tx.get("user_wallet") or "unknown",
                    store_id=tx.get("store_id") or "unknown",
                    status=tx.get("status") or "pending",
                    qr_type=tx.get("qr_type") or "backend",
                    amount=tx.get("amount_sol"),
                )
        except Exception as e:
            print(f"Error saving transaction data: {e}")
    
    def load_transaction_data():
        """Legacy loader kept for compatibility; data now comes from Supabase."""
        return []
    
    async def trigger_real_nft_mint(wallet: str, rarity: str, signature: str):
        """Trigger real NFT minting using Node.js Metaplex script.
        
        This runs alongside the existing Python-based NFT system.
        Does not replace or interfere with existing functionality.
        """
        try:
            print("🚀 Triggering real NFT mint...")
            print(f"   Wallet: {wallet}")
            print(f"   Rarity: {rarity}")
            print(f"   Signature: {signature}")
            
            # 3-second delay for devnet stability
            print("⏳ Waiting for devnet stability...")
            await asyncio.sleep(3)
            
            # Call Node.js minting script
            import subprocess
            
            print("🔨 Calling Node.js mint script...")
            result = subprocess.run(
                ["node", "nft_engine/mint.js", wallet, rarity],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=BASE_DIR  # Run from project root
            )
            
            if result.returncode == 0:
                print("✅ Real NFT minted successfully!")
                print(f"   Output: {result.stdout.strip()}")
                return True
            else:
                stderr = (result.stderr or "").strip()
                short_error = "\n".join(stderr.splitlines()[:4])
                print(f"❌ Real NFT minting failed (exit_code={result.returncode})")
                print(f"   Error: {short_error}")
                if "ERR_MODULE_NOT_FOUND" in stderr or "@solana/web3.js" in stderr:
                    print("💡 Node dependencies missing. Run: cd nft_engine && npm install")
                return False
                
        except subprocess.TimeoutExpired:
            print("❌ Real NFT minting timeout (30s)")
            return False
        except FileNotFoundError:
            print("❌ Node.js or mint.js not found - check installation")
            return False
        except Exception as e:
            print(f"❌ Real NFT minting error: {e}")
            return False
    
    async def trigger_nft_mint(validation_request, amount_received):
        """Trigger NFT minting based on validated transaction"""
        try:
            # Import NFT minter
            from nft_minting.nft_minter import NFTMinter
            
            # Determine NFT type based on amount
            if amount_received >= 0.1:
                nft_type = "epic_mystery"
            elif amount_received >= 0.05:
                nft_type = "rare_mystery"
            else:
                nft_type = "common_mystery"
            
            # Initialize NFT minter
            nft_minter = NFTMinter()
            nft_minter.load_or_create_minter_keypair()
            
            # Mint mystery NFT
            nft_result = await nft_minter.mint_mystery_nft(
                user_wallet=validation_request.wallet,
                nft_type=nft_type,
                transaction_signature=validation_request.signature,
                amount_paid=amount_received
            )
            
            return {
                "success": True,
                "nft_data": nft_result
            }
            
        except Exception as e:
            print(f"❌ NFT minting failed: {e}")
            return {"success": False, "error": str(e)}
    
    # Initialize FastAPI app
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.transaction_watcher = asyncio.create_task(transaction_watcher())
        try:
            yield
        finally:
            task = getattr(app.state, "transaction_watcher", None)
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(
        title="SolClub Loyalty Backend",
        description="Production Solana loyalty program with blockchain transactions",
        version="2.0.0",
        lifespan=lifespan,
    )

    loyalty_core = LoyaltyRulesEngine(use_sqlite=False)
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_middleware(GZipMiddleware, minimum_size=1024)

    allowed_hosts = os.getenv("ALLOWED_HOSTS", "*").strip()
    if allowed_hosts:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=[h.strip() for h in allowed_hosts.split(",") if h.strip()],
        )

    if os.getenv("FORCE_HTTPS", "false").lower() in {"1", "true", "yes"}:
        app.add_middleware(HTTPSRedirectMiddleware)

    try:
        from backend.client_merchant_platform import router as client_merchant_router
        app.include_router(client_merchant_router)
    except Exception as exc:
        print(f"⚠️ Platform router not loaded: {exc}")

    try:
        ui_static_dir = os.path.join(BASE_DIR, "frontend", "static")
        app.mount("/ui/static", StaticFiles(directory=ui_static_dir), name="ui-static")
        from backend.frontend_ui import router as frontend_ui_router
        app.include_router(frontend_ui_router)
    except Exception as exc:
        print(f"⚠️ Frontend UI router not loaded: {exc}")

    @app.middleware("http")
    async def merchant_route_guard(request: Request, call_next):
        path = request.url.path or ""
        is_merchant_page = path.startswith("/ui/merchant")
        is_merchant_api = path.startswith("/ui/api/merchant")

        if is_merchant_page or is_merchant_api:
            role = (
                request.headers.get("x-solclub-role")
                or request.cookies.get("solclub_role")
                or "client"
            ).strip().lower()

            if role != "merchant":
                if is_merchant_api:
                    return JSONResponse(
                        status_code=403,
                        content={"detail": "Merchant authentication required for this route."},
                    )
                return RedirectResponse(url="/ui/auth?required=merchant", status_code=307)

        return await call_next(request)

    async def transaction_watcher():
        """Background task to detect and process new merchant transactions."""
        # Track processed transactions for real NFT minting (duplicate prevention)
        minted_signatures = set()
        
        while True:
            try:
                if MERCHANT_WALLET is None:
                    print("⚠️ Merchant wallet not configured, skipping check")
                    await asyncio.sleep(10)
                    continue

                signatures_resp = await SOLANA_CLIENT.get_signatures_for_address(
                    MERCHANT_WALLET,
                    limit=20,
                )

                if not signatures_resp or not signatures_resp.value:
                    await asyncio.sleep(10)
                    continue

                fetched_count = len(signatures_resp.value)
                skipped_existing = 0
                processed_new = 0

                for signature_info in signatures_resp.value:
                    signature = str(signature_info.signature)

                    # Skip already processed transactions
                    if transaction_exists(signature):
                        skipped_existing += 1
                        continue

                    processed_new += 1
                    print(f"🆕 Processing new transaction: {signature[:16]}...")
                    try:
                        sig_obj = Signature.from_string(signature)
                    except Exception as exc:
                        print(f"❌ Invalid signature format {signature}: {exc}")
                        continue

                    tx_resp = await SOLANA_CLIENT.get_transaction(
                        sig_obj,
                        commitment=COMMITMENT,
                        max_supported_transaction_version=0,
                    )

                    if not tx_resp or not tx_resp.value:
                        print("❌ Transaction not found")
                        continue

                    tx_data = tx_resp.value
                    metadata = None
                    if tx_data.transaction and hasattr(tx_data.transaction, "meta"):
                        metadata = tx_data.transaction.meta

                    if metadata and metadata.err:
                        print(f"❌ Transaction has blockchain error: {metadata.err}")
                        continue

                    print("✅ Transaction fetched successfully")

                    tx_amount = 0.01
                    if metadata and metadata.pre_balances and metadata.post_balances:
                        balance_change = metadata.post_balances[1] - metadata.pre_balances[1]
                        tx_amount = abs(balance_change) / 1_000_000_000

                    user_wallet = None
                    try:
                        account_keys = tx_data.transaction.transaction.message.account_keys
                        if account_keys and len(account_keys) > 0:
                            user_wallet = str(account_keys[0])
                    except Exception as exc:
                        print(f"⚠️ Could not extract wallet from account_keys: {exc}")

                    if not user_wallet:
                        print("⚠️ Could not determine buyer wallet from transaction; using fallback merchant wallet")
                        user_wallet = str(MERCHANT_WALLET) if MERCHANT_WALLET else "unknown"

                    print("👤 User wallet detected:", user_wallet)

                    insert_transaction(
                        wallet=user_wallet,
                        merchant_id=1,
                        amount=tx_amount,
                        signature=signature,
                    )

                    print("💾 Transaction saved to DB")

                    try:
                        decision = loyalty_core.evaluate_cashback_and_nft(
                            wallet=user_wallet,
                            merchant_id=1,
                            transaction_amount=tx_amount,
                        )
                        save_cashback_reward(
                            wallet=user_wallet,
                            merchant_id=1,
                            transaction_signature=signature,
                            transaction_amount=tx_amount,
                            cashback_amount=decision.cashback_amount,
                            reward_tier=decision.reward_tier,
                        )
                        print(
                            f"💸 Cashback recorded: {decision.cashback_amount} SOL "
                            f"({decision.reward_tier}, {decision.cashback_rate * 100:.2f}%)"
                        )
                    except Exception as cashback_exc:
                        print(f"⚠️ Cashback evaluation skipped: {cashback_exc}")

                    # EXISTING: Python-based NFT minting (DB storage)
                    minted_nft = await mint_nft(
                        wallet=user_wallet,
                        amount_paid=tx_amount,
                        transaction_signature=signature,
                    )

                    if minted_nft:
                        print("🎁 DB NFT record created successfully")
                    else:
                        print("❌ DB NFT record creation failed")

                    # NEW: Real blockchain NFT minting (Node.js + Metaplex)
                    # Only proceed if we haven't already minted for this transaction
                    if signature not in minted_signatures:
                        try:
                            # Get user's transaction count for rarity calculation
                            user_tx_count = max(count_wallet_transactions(user_wallet), 1)
                            
                            # Calculate rarity using loyalty engine (same logic as mint_nft)
                            from loyalty_engine.loyalty_engine import get_nft_rarity
                            rarity = get_nft_rarity(user_tx_count)
                            
                            # Convert to metadata tier format (common, mystery, epic, legendary)
                            rarity_mapping = {
                                "common_mystery": "common",
                                "rare_mystery": "mystery", 
                                "epic_mystery": "epic",
                                "legendary_mystery": "legendary"
                            }
                            metadata_rarity = rarity_mapping.get(rarity, "common")
                            
                            print(f"🎲 Calculated rarity: {rarity} → {metadata_rarity}")
                            
                            # Trigger real NFT minting
                            real_mint_success = await trigger_real_nft_mint(
                                wallet=user_wallet,
                                rarity=metadata_rarity,
                                signature=signature
                            )
                            
                            if real_mint_success:
                                # Mark as processed to prevent duplicates
                                minted_signatures.add(signature)
                                print("✅ Real NFT minting completed")
                            else:
                                print("⚠️ Real NFT minting failed, will retry on next detection")
                                
                        except Exception as real_mint_error:
                            print(f"⚠️ Real NFT minting setup failed: {real_mint_error}")
                            print("   Continuing with transaction processing...")
                    else:
                        print("⏭️ Real NFT already minted for this transaction")

                if processed_new > 0 or skipped_existing > 0:
                    print(
                        "🔎 Watcher summary: "
                        f"fetched={fetched_count}, new={processed_new}, skipped={skipped_existing}"
                    )

            except Exception as exc:
                print(f"❌ Transaction watcher error: {exc}")

            await asyncio.sleep(10)

    @app.get("/")
    async def root():
        """API information and status"""
        return {
            "name": "SolClub Loyalty Backend",
            "version": "2.0.0",
            "status": "ACTIVE",
            "features": [
                "Solana Pay QR codes",
                "Blockchain transaction validation",
                "Mystery NFT minting system",
                "Seasonal collections",
                "Multi-tier rewards"
            ],
            "endpoints": {
                "GET /": "API information",
                "GET /ui/client": "Client dashboard",
                "GET /ui/merchant": "Merchant dashboard",
                "GET /ui/auth": "Authentication dashboard",
                "GET /solana-pay-request": "Handle QR code scans",
                "POST /validate-transaction": "Blockchain validation",
                "POST /wallet-connect": "Wallet registration",
                "GET /mystery-nft/{wallet}": "User's NFT collection",
                "GET /seasonal-drops": "Active collections"
            },
            "testing": {
                "network": "Solana devnet",
                "free_testing": True,
                "wallet_support": ["Phantom", "Solflare", "Any Solana wallet"]
            }
        }
    
    @app.get("/solana-pay-request")
    async def handle_solana_pay_request(
        reference: str = None,
        amount: float = None
    ):
        """Handle QR code scans from Solana Pay wallets"""
        try:
            return {
                "success": True,
                "message": "Solana Pay request received",
                "reference": reference,
                "amount": amount,
                "next_steps": [
                    "Complete transaction in wallet",
                    "Backend will validate payment",
                    "Mystery NFT will be minted automatically"
                ]
            }
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/validate-transaction")
    async def validate_transaction(request: ValidationRequest):
        """Validate actual Solana blockchain transaction and mint rewards"""
        try:
            print(f"🔍 Validating transaction: {request.signature}")

            # Demo flow bypass for local testing
            if str(request.signature).startswith("demo_"):
                valid = True
                tx_amount = float(request.amount or 0.01)
                transaction = type("DemoTx", (), {
                    "meta": None,
                    "block_time": None,
                    "slot": None
                })()
            else:
                valid = False

                # Convert string signature to Signature object for RPC call
                try:
                    sig = Signature.from_string(request.signature)
                except Exception as exc:
                    return {
                        "valid": False,
                        "error": "Invalid signature format",
                        "signature": request.signature,
                        "details": str(exc)
                    }

                # Get transaction from blockchain
                tx_response = await SOLANA_CLIENT.get_transaction(
                    sig,
                    commitment=COMMITMENT,
                    max_supported_transaction_version=0
                )

                if not tx_response.value:
                    return {
                        "valid": False,
                        "error": "Transaction not found on blockchain",
                        "signature": request.signature
                    }

                tx_data = tx_response.value

                if not tx_data:
                    return {
                        "valid": False,
                        "error": "Transaction not found on blockchain",
                        "signature": request.signature
                    }

                # Solders response carries transaction inside tx_data.transaction
                metadata = None
                if tx_data.transaction and hasattr(tx_data.transaction, "meta"):
                    metadata = tx_data.transaction.meta

                # Validate transaction was successful
                if metadata and metadata.err:
                    return {
                        "valid": False,
                        "error": "Transaction failed on blockchain",
                        "signature": request.signature,
                        "blockchain_error": str(metadata.err)
                    }

                valid = True

                # Calculate amount from actual blockchain change when available
                tx_amount = 0.01
                if metadata and metadata.pre_balances and metadata.post_balances:
                    balance_change = metadata.post_balances[1] - metadata.pre_balances[1]
                    tx_amount = abs(balance_change) / 1_000_000_000  # Convert lamports to SOL

                transaction = tx_data

            
            # Save transaction in central DB
            merchant_id = request.merchant_id or 0
            insert_transaction(
                wallet=request.wallet,
                merchant_id=max(merchant_id, 1),
                amount=tx_amount,
                signature=request.signature,
            )

            try:
                decision = loyalty_core.evaluate_cashback_and_nft(
                    wallet=request.wallet,
                    merchant_id=max(merchant_id, 1),
                    transaction_amount=tx_amount,
                )
                save_cashback_reward(
                    wallet=request.wallet,
                    merchant_id=max(merchant_id, 1),
                    transaction_signature=request.signature,
                    transaction_amount=tx_amount,
                    cashback_amount=decision.cashback_amount,
                    reward_tier=decision.reward_tier,
                )
            except Exception as cashback_exc:
                print(f"⚠️ Cashback evaluation skipped: {cashback_exc}")

            # Mint one NFT reward based on transaction history
            minted_nft = await mint_nft(
                wallet=request.wallet,
                amount_paid=tx_amount,
                transaction_signature=request.signature,
            )

            # Return simplified success payload (reference not required)
            return {
                "status": "success",
                "nft_reward": "minted" if minted_nft else "failed"
            }
            
        except Exception as e:
            print(f"❌ Transaction validation error: {e}")
            return {
                "valid": False,
                "error": f"Validation failed: {str(e)}",
                "signature": request.signature
            }
    
    @app.post("/wallet-connect")
    async def connect_wallet(request: WalletConnectRequest):
        """Register wallet in loyalty program"""
        try:
            existing_user = get_client_profile(request.publicKey)
            if existing_user:
                return {
                    "success": True,
                    "message": "Welcome back!",
                    "user": existing_user
                }

            upsert_client_profile(request.publicKey, joined_date=datetime.now().isoformat(), loyalty_tier="bronze")
            user_data = get_client_profile(request.publicKey) or {
                "wallet_address": request.publicKey,
                "joined_date": datetime.now().isoformat(),
                "loyalty_tier": "bronze",
                "status": "active",
            }
            
            return {
                "success": True,
                "message": "Wallet connected successfully!",
                "user": user_data,
                "welcome_bonus": {
                    "description": "Complete your first purchase to receive a mystery NFT!",
                    "qr_codes_available": 3
                }
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/mystery-nft/{wallet}")
    async def get_user_nfts(wallet: str):
        """Get user's mystery NFT collection"""
        try:
            normalized_wallet = wallet.strip()
            user_nfts = list_nft_records(normalized_wallet)

            rarity_counts = {}
            for nft in user_nfts:
                rarity = nft.get("nft_type", nft.get("rarity", "unknown"))
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1

            return {
                "wallet": normalized_wallet,
                "nfts": user_nfts,
                "total_count": len(user_nfts),
                "rarity_breakdown": rarity_counts,
                "unrevealed_count": len([n for n in user_nfts if not n.get("mystery_revealed", False)]),
            }

        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.get("/seasonal-drops")
    async def get_seasonal_drops():
        """Get active seasonal NFT collections"""
        try:
            seasonal_collections = {
                "winter_2024": {
                    "name": "Winter Wonderland",
                    "description": "Magical winter-themed mystery NFTs",
                    "active": False,
                    "period": "December 2024 - February 2025",
                    "themes": ["snowflake", "ice_crystal", "winter_aurora"]
                },
                "spring_2025": {
                    "name": "Spring Bloom",
                    "description": "Fresh spring awakening collection",
                    "active": True,
                    "period": "March 2025 - May 2025",
                    "themes": ["cherry_blossom", "spring_rain", "butterfly"]
                },
                "loyalty_legends": {
                    "name": "Loyalty Legends",
                    "description": "Exclusive loyalty program achievements",
                    "active": True,
                    "max_supply": 10000,
                    "themes": ["bronze_legend", "silver_legend", "gold_legend", "platinum_legend"]
                }
            }
            
            return {
                "seasonal_collections": seasonal_collections,
                "active_count": len([c for c in seasonal_collections.values() if c.get("active", False)]),
                "message": "Complete purchases to earn mystery NFTs from active collections!"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
    @app.post("/reveal-mystery/{mint_address}")
    async def reveal_mystery_nft(mint_address: str, wallet: str = Query(...)):
        """Reveal a mystery NFT if reveal time has passed"""
        try:
            # Import NFT minter
            from nft_minting.nft_minter import NFTMinter
            
            minter = NFTMinter()
            revealed_nft = await minter.reveal_mystery_nft(mint_address)
            
            if not revealed_nft:
                raise HTTPException(status_code=404, detail="NFT not found or cannot be revealed yet")
            
            if revealed_nft["owner"] != wallet:
                raise HTTPException(status_code=403, detail="You don't own this NFT")
            
            return {
                "success": True,
                "mint_address": mint_address,
                "revealed_at": revealed_nft.get("revealed_at"),
                "nft_data": revealed_nft,
                "message": "🎉 Mystery NFT revealed!"
            }
            
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Reveal failed: {str(e)}")
    
    @app.get("/transaction-request")
    async def transaction_request(
        user_wallet: str = Query(..., description="User's Solana wallet address"),
        store_id: str = Query(..., description="Store identifier"),
        reference: str = Query(..., description="Transaction reference key")
    ):
        """Handle transaction request from QR code scan"""
        try:
            # Validate wallet address
            try:
                Pubkey.from_string(user_wallet)
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid wallet address")
            
            save_payment_request(
                reference=reference,
                user_wallet=user_wallet,
                store_id=store_id,
                status="initiated",
                qr_type="backend",
            )
            
            # Return Solana Pay response format
            return {
                "label": "SolClub Loyalty Purchase",
                "icon": "https://solclub.example.com/icon.png",
                "message": "Complete your purchase to earn loyalty NFTs!",
                "reference": reference,
                "user_wallet": user_wallet,
                "store_id": store_id,
                "status": "ready_for_payment"
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Transaction request failed: {str(e)}")
    
    @app.get("/user/{wallet}/stats")
    async def get_user_stats(wallet: str):
        """Get user's loyalty program statistics"""
        try:
            normalized_wallet = wallet.strip()
            user_nfts = list_nft_records(normalized_wallet)
            user_transactions = list_wallet_transactions(normalized_wallet, limit=200)
            
            # Calculate statistics
            total_spent = sum(float(tx.get("amount", 0) or 0) for tx in user_transactions)
            nft_counts = {}
            for nft in user_nfts:
                nft_type = nft.get("nft_type", "unknown")
                nft_counts[nft_type] = nft_counts.get(nft_type, 0) + 1
            
            # Determine loyalty tier
            loyalty_tier = "Bronze"
            if total_spent >= 1.0:
                loyalty_tier = "Platinum"
            elif total_spent >= 0.5:
                loyalty_tier = "Gold"
            elif total_spent >= 0.25:
                loyalty_tier = "Silver"
            
            return {
                "wallet": wallet,
                "loyalty_tier": loyalty_tier,
                "total_transactions": len(user_transactions),
                "total_spent": total_spent,
                "total_nfts": len(user_nfts),
                "nft_breakdown": nft_counts,
                "recent_transactions": user_transactions[:5],
                "unrevealed_nfts": len([nft for nft in user_nfts if not nft.get("mystery_revealed", False)]),
                "next_milestone": get_next_milestone(total_spent)
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get user stats: {str(e)}")

    @app.post("/merchant/register")
    async def register_merchant(name: str, wallet_address: str):
        """Register a merchant and return api_key"""
        try:
            api_key = uuid.uuid4().hex
            create_merchant(name=name, wallet_address=wallet_address, api_key=api_key)

            return {"success": True, "api_key": api_key}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/merchant/{merchant_id}")
    async def get_merchant(merchant_id: int):
        """Fetch merchant details by id"""
        row = db_get_merchant_by_id(merchant_id)
        if not row:
            raise HTTPException(status_code=404, detail="Merchant not found")
        return row

    @app.get("/merchant/by-name/{name}")
    async def get_merchant_by_name(name: str):
        """Fetch merchant details by name"""
        row = db_get_merchant_by_name(name)
        if not row:
            raise HTTPException(status_code=404, detail="Merchant not found")
        return row

    @app.get("/customer/{wallet}")
    async def get_customer(wallet: str):
        """Fetch customer data with NFT history and tier"""
        normalized_wallet = wallet.strip()
        nfts = list_nft_records(normalized_wallet)

        total_transactions = len(nfts)

        # Determine tier from loyalty engine
        try:
            from loyalty_engine.loyalty_engine import LoyaltyRulesEngine
            loyalty_engine = LoyaltyRulesEngine(use_sqlite=False)
            tier = loyalty_engine.calculate_tier(total_transactions)
        except Exception:
            # fallback simple local tier mapping
            if total_transactions >= 20:
                tier = "platinum"
            elif total_transactions >= 10:
                tier = "gold"
            elif total_transactions >= 5:
                tier = "silver"
            else:
                tier = "bronze"

        return {
            "wallet": normalized_wallet,
            "total_transactions": total_transactions,
            "tier": tier,
            "nfts": nfts
        }

    def get_next_milestone(total_spent):
        """Calculate next spending milestone"""
        milestones = [0.25, 0.5, 1.0, 2.0, 5.0]
        
        for milestone in milestones:
            if total_spent < milestone:
                return {
                    "amount_needed": milestone - total_spent,
                    "milestone": milestone,
                    "reward": f"Loyalty tier upgrade at {milestone} SOL"
                }
        
        return {
            "amount_needed": 0,
            "milestone": "max",
            "reward": "Maximum tier reached!"
        }
    
    @app.get("/health")
    async def health_check():
        """System health check with blockchain connectivity"""
        try:
            # Check Solana connection
            latest_blockhash = await SOLANA_CLIENT.get_latest_blockhash()
            blockchain_status = "connected" if latest_blockhash.value else "disconnected"

            db_status = "connected"
            stats_preview = {}
            try:
                stats_preview = get_platform_stats()
            except Exception as db_exc:
                db_status = f"error: {db_exc}"
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "api": "online",
                    "blockchain": blockchain_status,
                    "database": db_status,
                    "merchant_wallet": str(MERCHANT_WALLET) if MERCHANT_WALLET else "not_configured"
                },
                "stats_preview": {
                    "total_users": stats_preview.get("total_users", 0),
                    "total_transactions": stats_preview.get("total_transactions", 0),
                },
                "version": "2.0.0"
            }
            
        except Exception as e:
            return {
                "status": "degraded",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    return app


app = create_fastapi_app()

async def generate_qr():
    """Generate Solana Pay QR codes"""
    print("📸 QR Code Generator")
    print("-" * 30)
    
    try:
        # Add modules to path
        from qr_wallet.qr_generator import SolanaPayQRGenerator
        
        generator = SolanaPayQRGenerator()
        print(f"💳 Merchant Wallet: {generator.merchant_wallet}")
        
        # Interactive QR generation
        while True:
            print("\nQR Code Options:")
            print("1. Coffee Shop (0.01 SOL)")
            print("2. Bookstore (0.05 SOL)")
            print("3. Electronics (0.1 SOL)")
            print("4. Custom amount")
            print("5. Unlimited / Any Amount QR")
            print("0. Exit")
            
            choice = input("\nSelect option: ").strip()
            
            if choice == "0":
                break
            elif choice == "1":
                await generate_store_qr(generator, 0.01, "coffee_shop", "Coffee + Mystery NFT")
            elif choice == "2":
                await generate_store_qr(generator, 0.05, "bookstore", "Book + Rare Mystery NFT")
            elif choice == "3":
                await generate_store_qr(generator, 0.1, "electronics", "Gadget + Epic Mystery NFT")
            elif choice == "4":
                amount = float(input("Enter amount in SOL: "))
                store = input("Store ID: ")
                product = input("Product name: ")
                await generate_store_qr(generator, amount, store, product)
            elif choice == "5":
                store = input("Store ID: ")
                product = input("Product name: ")
                await generate_dynamic_qr(generator, store, product)
            else:
                print("Invalid option")
        
        await generator.client.close()
        
    except Exception as e:
        print(f"❌ QR generation failed: {e}")

async def generate_dynamic_qr(generator, store_id: str, product: str):
    """Generate a dynamic Solana Pay QR that lets the user enter the amount manually."""
    try:
        print(f"\n📸 Generating dynamic QR for: {product}")
        solana_url, reference = generator.create_solana_pay_url(
            store_id=store_id,
            product_name=product
        )
        qr_filename = f"main_{store_id}_dynamic.png"
        qr_path = generator.generate_qr_code(solana_url, qr_filename, "main")
        print("✅ Dynamic QR generated (user will enter amount in wallet)")
        print(f"✅ QR Code saved: {qr_path}")
        print(f"🔗 Solana Pay URL: {solana_url}")
        print(f"📱 Scan with any Solana wallet!")
    except Exception as e:
        print(f"❌ Failed to generate dynamic QR: {e}")

async def generate_store_qr(generator, amount: float, store_id: str, product: str):
    """Generate QR code for a specific store"""
    try:
        print(f"\n📸 Generating QR for: {product}")
        
        # Create Solana Pay URL
        solana_url, reference = generator.create_solana_pay_url(
            amount_sol=amount,
            store_id=store_id,
            product_name=product
        )
        
        # Generate QR code
        qr_filename = f"main_{store_id}.png"
        qr_path = generator.generate_qr_code(solana_url, qr_filename, "main")
        
        print(f"✅ QR Code saved: {qr_path}")
        print(f"🔗 Solana Pay URL: {solana_url}")
        print(f"📱 Scan with any Solana wallet!")
        
    except Exception as e:
        print(f"❌ Failed to generate QR: {e}")

async def mint_mystery_nft():
    """Mint mystery NFTs via interactive CLI.

    This command replaces the previous hard‑coded flow by asking the user for a
    wallet, validating the address, logging the attempt, and printing a clean
    summary on success.  Any problem stops the operation with an informative
    message.
    """

    print("🎨 Mystery NFT Minter")
    print("-" * 30)

    try:
        # dynamic imports only when command is invoked
        from nft_minting.nft_minter import NFTMinter, WalletValidator, logger
        from datetime import datetime

        minter = NFTMinter()
        minter.load_or_create_minter_keypair()
        logger.info("starting mint command")

        print(f"🔑 NFT Minter pubkey: {minter.keypair.pubkey() if minter.keypair else 'none'}")

        # --- wallet input & validation ------------------------------------------------
        wallet = input("Enter user wallet address: ").strip()
        if not WalletValidator.is_valid(wallet):
            print(f"❌ Invalid wallet address: {wallet}")
            logger.error("user entered invalid wallet: %s", wallet)
            return
        logger.info("wallet validated: %s", wallet)

        # --- rarity selection --------------------------------------------------------
        print("\nMystery NFT Types:")
        print("1. Common Mystery (60% chance)")
        print("2. Rare Mystery (30% chance)")
        print("3. Epic Mystery (8% chance)")
        print("4. Legendary Mystery (2% chance)")
        print("5. Random (weighted by rarity engine)")

        choice = input("Select type (1-5): ").strip()
        nft_types = {
            "1": "common_mystery",
            "2": "rare_mystery",
            "3": "epic_mystery",
            "4": "legendary_mystery",
            "5": None,  # let engine choose
        }

        nft_type = nft_types.get(choice)
        if nft_type is None and choice == "5":
            nft_type = minter.determine_mystery_rarity(amount_paid=0.01, user_transaction_count=1)
        elif nft_type is None:
            print("❌ Invalid selection, aborting.")
            logger.warning("invalid rarity choice: %s", choice)
            return

        print(f"\n🎲 Minting {nft_type} NFT for {wallet} ...")

        # debug: verify exact wallet from input is used
        print("DEBUG USER WALLET:", wallet)

        # perform mint
        nft = await minter.mint_mystery_nft(
            user_wallet=wallet,
            nft_type=nft_type,
            transaction_signature=f"main_mint_{int(asyncio.get_event_loop().time())}",
            amount_paid=0.01,
        )

        if nft:
            ts = datetime.now().isoformat()
            print("✅ Mystery NFT minted successfully!")
            print(f"   Wallet       : {wallet}")
            print(f"   Rarity       : {nft['nft_type']}")
            print(f"   Timestamp    : {ts}")
            if nft.get("seasonal_theme"):
                print(f"   Seasonal     : {nft['seasonal_theme']}")
            logger.info("mint success wallet=%s rarity=%s time=%s", wallet, nft['nft_type'], ts)
        else:
            print("❌ NFT minting failed")
            logger.error("mint returned no record for wallet %s", wallet)

        await minter.client.close()

    except Exception as e:
        print(f"❌ NFT minting failed: {e}")
        try:
            logger.exception("exception in mint command")
        except NameError:
            pass

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="SolClub - Real Solana Loyalty Program",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py demo     # Run comprehensive demo
  python main.py server   # Start API server
  python main.py qr       # Generate QR codes
  python main.py mint     # Mint mystery NFTs
        """
    )
    
    parser.add_argument(
        'command',
        nargs='?',
        default='help',
        choices=['demo', 'server', 'qr', 'mint', 'help'],
        help='Command to execute'
    )
    
    args = parser.parse_args()
    
    show_banner()
    
    if args.command == 'help':
        show_help()
    elif args.command == 'demo':
        asyncio.run(run_demo())
    elif args.command == 'server':
        start_server()
    elif args.command == 'qr':
        asyncio.run(generate_qr())
    elif args.command == 'mint':
        asyncio.run(mint_mystery_nft())
    else:
        print(f"Unknown command: {args.command}")
        show_help()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Thanks for using SolClub!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)