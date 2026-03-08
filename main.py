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

import sys
import asyncio
import argparse
from typing import Optional

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
        
        # Create FastAPI app directly in main.py
        app = create_fastapi_app()
        
        print("📱 Ready for mobile wallet connections!")
        print("🔗 API Documentation: http://localhost:8000/docs")
        print("✨ This backend handles Solana transactions!")
        
        uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
        
    except ImportError as e:
        print(f"❌ Server not available: {e}")
        print("Install dependencies: pip install fastapi uvicorn")
    except Exception as e:
        print(f"❌ Server failed to start: {e}")

def create_fastapi_app():
    """Create and configure the FastAPI application with full blockchain integration"""
    from fastapi import FastAPI, HTTPException, Query
    from fastapi.middleware.cors import CORSMiddleware
    from pydantic import BaseModel
    from typing import Optional, Dict, Any, List
    import json
    import os
    import asyncio
    from datetime import datetime, timedelta
    from solana.rpc.async_api import AsyncClient
    from solana.rpc.commitment import Commitment
    from solders.pubkey import Pubkey
    from solders.keypair import Keypair
    
    # Pydantic models
    class ValidationRequest(BaseModel):
        signature: str
        reference: str
        wallet: str

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
    SOLANA_CLIENT = AsyncClient("https://api.devnet.solana.com")
    COMMITMENT = Commitment("confirmed")
    
    # Load merchant keypair
    def load_merchant_keypair():
        keypair_path = "data/merchant_keypair.json"
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
        """Save transaction data to JSON file"""
        try:
            transactions_file = "data/transactions.json"
            os.makedirs(os.path.dirname(transactions_file), exist_ok=True)
            
            # Load existing transactions
            existing_transactions = []
            if os.path.exists(transactions_file):
                with open(transactions_file, 'r') as f:
                    existing_transactions = json.load(f)
            
            # Add new transactions
            existing_transactions.extend(transactions)
            
            # Save back to file
            with open(transactions_file, 'w') as f:
                json.dump(existing_transactions, f, indent=2)
                
        except Exception as e:
            print(f"Error saving transaction data: {e}")
    
    def load_transaction_data():
        """Load transaction metadata from JSON file"""
        data_file = "data/transactions.json"
        if os.path.exists(data_file):
            with open(data_file, 'r') as f:
                return json.load(f)
        return []
    
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
    app = FastAPI(
        title="SolClub Loyalty Backend",
        description="Production Solana loyalty program with blockchain transactions",
        version="2.0.0"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
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
            
            # Get transaction from blockchain
            tx_response = await SOLANA_CLIENT.get_transaction(
                request.signature,
                commitment=COMMITMENT,
                max_supported_transaction_version=0
            )
            
            if not tx_response.value:
                return {
                    "valid": False,
                    "error": "Transaction not found on blockchain",
                    "signature": request.signature
                }
            
            transaction = tx_response.value
            
            # Validate transaction was successful
            if transaction.meta and transaction.meta.err:
                return {
                    "valid": False,
                    "error": "Transaction failed on blockchain",
                    "signature": request.signature,
                    "blockchain_error": str(transaction.meta.err)
                }
            
            # Extract transaction amount (simplified calculation)
            tx_amount = 0.01  # Default amount for demo
            if transaction.meta and transaction.meta.pre_balances and transaction.meta.post_balances:
                # Calculate actual amount transferred
                balance_change = transaction.meta.post_balances[1] - transaction.meta.pre_balances[1]
                tx_amount = abs(balance_change) / 1_000_000_000  # Convert lamports to SOL
            
            # Trigger NFT minting process
            nft_result = await trigger_nft_mint(request, tx_amount)
            
            return {
                "valid": True,
                "signature": request.signature,
                "amount_received": tx_amount,
                "block_time": transaction.block_time,
                "slot": transaction.slot,
                "reference": request.reference,
                "nft_minted": nft_result.get("success", False),
                "nft_details": nft_result.get("nft_data") if nft_result.get("success") else None,
                "message": "🎉 Transaction validated and mystery NFT minted!" if nft_result.get("success") else "Transaction validated but NFT minting failed"
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
            # Load or create user data
            user_data = {
                "wallet": request.publicKey,
                "joined_date": datetime.now().isoformat(),
                "loyalty_tier": "bronze",
                "total_spent": 0.0,
                "nft_count": 0,
                "status": "active"
            }
            
            # Save user data
            users_file = "data/loyalty_users.json"
            os.makedirs(os.path.dirname(users_file), exist_ok=True)
            
            users = []
            if os.path.exists(users_file):
                with open(users_file, 'r') as f:
                    users = json.load(f)
            
            # Check if user already exists
            existing_user = next((u for u in users if u["wallet"] == request.publicKey), None)
            if existing_user:
                return {
                    "success": True,
                    "message": "Welcome back!",
                    "user": existing_user
                }
            
            users.append(user_data)
            with open(users_file, 'w') as f:
                json.dump(users, f, indent=2)
            
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
            nft_file = "data/nft_records.json"
            
            if not os.path.exists(nft_file):
                return {
                    "wallet": wallet,
                    "nfts": [],
                    "total_count": 0,
                    "message": "No NFTs found. Complete a purchase to receive your first mystery NFT!"
                }
            
            with open(nft_file, 'r') as f:
                all_nfts = json.load(f)
            
            # Filter NFTs for this wallet
            user_nfts = [nft for nft in all_nfts if nft.get("owner") == wallet]
            
            # Count by rarity
            rarity_counts = {}
            for nft in user_nfts:
                rarity = nft.get("nft_type", "unknown")
                rarity_counts[rarity] = rarity_counts.get(rarity, 0) + 1
            
            return {
                "wallet": wallet,
                "nfts": user_nfts,
                "total_count": len(user_nfts),
                "rarity_breakdown": rarity_counts,
                "unrevealed_count": len([n for n in user_nfts if not n.get("revealed", False)])
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
            
            # Load existing transactions
            transactions = load_transaction_data()
            
            # Find the transaction with this reference
            transaction_found = False
            for tx in transactions:
                if tx.get("reference") == reference:
                    tx["user_wallet"] = user_wallet
                    tx["store_id"] = store_id
                    tx["status"] = "initiated"
                    tx["initiated_at"] = datetime.now().isoformat()
                    transaction_found = True
                    break
            
            if not transaction_found:
                # Create new transaction record
                new_tx = {
                    "reference": reference,
                    "user_wallet": user_wallet,
                    "store_id": store_id,
                    "status": "initiated",
                    "initiated_at": datetime.now().isoformat(),
                    "qr_type": "backend"
                }
                transactions.append(new_tx)
            
            save_transaction_data(transactions)
            
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
            # Load user's NFTs and transaction history
            nft_file = "data/nft_records.json"
            transaction_file = "data/transactions.json"
            
            user_nfts = []
            user_transactions = []
            
            if os.path.exists(nft_file):
                with open(nft_file, 'r') as f:
                    all_nfts = json.load(f)
                user_nfts = [nft for nft in all_nfts if nft.get("owner") == wallet]
            
            if os.path.exists(transaction_file):
                with open(transaction_file, 'r') as f:
                    all_transactions = json.load(f)
                user_transactions = [tx for tx in all_transactions if tx.get("user_wallet") == wallet]
            
            # Calculate statistics
            total_spent = sum(tx.get("amount_sol", 0) for tx in user_transactions if tx.get("status") == "confirmed")
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
                "recent_transactions": user_transactions[-5:],  # Last 5 transactions
                "unrevealed_nfts": len([nft for nft in user_nfts if not nft.get("mystery_revealed", False)]),
                "next_milestone": get_next_milestone(total_spent)
            }
            
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to get user stats: {str(e)}")
    
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
            
            # Check data files
            required_files = ["data/nft_records.json", "data/transactions.json"]
            file_status = {}
            for file_path in required_files:
                file_status[file_path] = "exists" if os.path.exists(file_path) else "missing"
            
            return {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "services": {
                    "api": "online",
                    "blockchain": blockchain_status,
                    "merchant_wallet": str(MERCHANT_WALLET) if MERCHANT_WALLET else "not_configured"
                },
                "data_files": file_status,
                "version": "2.0.0"
            }
            
        except Exception as e:
            return {
                "status": "degraded",
                "timestamp": datetime.now().isoformat(),
                "error": str(e)
            }
    
    return app

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
            else:
                print("Invalid option")
        
        await generator.client.close()
        
    except Exception as e:
        print(f"❌ QR generation failed: {e}")

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
    """Mint mystery NFTs"""
    print("🎨 Mystery NFT Minter")
    print("-" * 30)
    
    try:
        # Add modules to path
        from nft_minting.nft_minter import NFTMinter
        
        minter = NFTMinter()
        minter.load_or_create_minter_keypair()
        
        print(f"🔑 NFT Minter: {minter.minter_keypair.public_key}")
        
        # Interactive NFT minting
        wallet = input("Enter user wallet address: ").strip()
        
        print("\nMystery NFT Types:")
        print("1. Common Mystery (60% chance)")
        print("2. Rare Mystery (30% chance)")
        print("3. Epic Mystery (8% chance)")
        print("4. Legendary Mystery (2% chance)")
        print("5. Random (based on rarity distribution)")
        
        choice = input("Select type: ").strip()
        
        nft_types = {
            "1": "common_mystery",
            "2": "rare_mystery", 
            "3": "epic_mystery",
            "4": "legendary_mystery",
            "5": None  # Random
        }
        
        nft_type = nft_types.get(choice)
        if nft_type is None and choice == "5":
            # Determine random rarity using default payment/loyalty values
            nft_type = minter.determine_mystery_rarity(amount_paid=0.01, user_transaction_count=1)
        elif nft_type is None:
            print("Invalid option")
            return
            
        print(f"\n🎲 Minting {nft_type} NFT...")
        
        nft = await minter.mint_mystery_nft(
            user_wallet=wallet,
            nft_type=nft_type,
            transaction_signature=f"main_mint_{int(asyncio.get_event_loop().time())}",
            amount_paid=0.01
        )
        
        if nft:
            print("✅ Mystery NFT minted successfully!")
            print(f"   Mint Address: {nft['mint_address']}")
            print(f"   Rarity: {nft['nft_type']}")
            print(f"   Reveal Date: {nft['reveal_date']}")
            if nft.get('seasonal_theme'):
                print(f"   Seasonal Theme: {nft['seasonal_theme']}")
        else:
            print("❌ NFT minting failed")
            
        await minter.client.close()
        
    except Exception as e:
        print(f"❌ NFT minting failed: {e}")

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