"""
MODULE 1: Solana Pay QR Generator
Generates actual Solana Pay QR codes that work with Phantom, Solflare, and other wallets
Production blockchain transactions on Solana devnet
"""

import qrcode
import base58
import os
from datetime import datetime
from solders.keypair import Keypair
from solders.pubkey import Pubkey
from urllib.parse import urlencode
import json
import asyncio
from solana.rpc.async_api import AsyncClient

class SolanaPayQRGenerator:
    def __init__(self, merchant_wallet=None, backend_url="http://localhost:8000"):
        self.backend_url = backend_url
        self.output_dir = "../data"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Use provided merchant wallet or create one
        if merchant_wallet:
            self.merchant_wallet = Pubkey.from_string(merchant_wallet)
        else:
            # Load or create merchant keypair
            self.merchant_keypair = self.load_or_create_merchant_keypair()
            self.merchant_wallet = self.merchant_keypair.pubkey()
        
        self.client = AsyncClient("https://api.devnet.solana.com")
    
    def load_or_create_merchant_keypair(self):
        """Load or create merchant keypair for receiving payments"""
        keypair_path = os.path.join(self.output_dir, "merchant_keypair.json")
        
        if os.path.exists(keypair_path):
            with open(keypair_path, 'r') as f:
                keypair_data = json.load(f)
                keypair = Keypair.from_bytes(bytes(keypair_data))
                print(f"✅ Loaded merchant wallet: {keypair.pubkey()}")
                return keypair
        else:
            keypair = Keypair()
            with open(keypair_path, 'w') as f:
                json.dump(list(bytes(keypair)), f)
            print(f"🔑 Created new merchant wallet: {keypair.pubkey()}")
            print("⚠️  IMPORTANT: Fund this wallet with devnet SOL for testing!")
            return keypair
    
    def generate_reference_key(self):
        """Generate a unique reference key for transaction tracking"""
        keypair = Keypair()
        return base58.b58encode(bytes(keypair.pubkey())).decode('utf-8')
    
    async def fund_merchant_wallet(self, amount_sol=5.0):
        """Request airdrop for merchant wallet (devnet only)"""
        try:
            print(f"💰 Requesting {amount_sol} SOL airdrop for merchant wallet...")
            response = await self.client.request_airdrop(
                self.merchant_wallet,
                int(amount_sol * 1_000_000_000)  # Convert to lamports
            )
            
            if response.value:
                print(f"✅ Airdrop successful: {response.value}")
                await asyncio.sleep(2)  # Wait for confirmation
                
                balance = await self.client.get_balance(self.merchant_wallet)
                print(f"💳 Merchant wallet balance: {balance.value / 1_000_000_000} SOL")
                return True
            else:
                print("❌ Airdrop failed")
                return False
        except Exception as e:
            print(f"❌ Airdrop error: {e}")
            return False
    
    def create_solana_pay_url(self, amount_sol=0.01, store_id="store_001", product_name="Loyalty Purchase"):
        """Create a REAL Solana Pay URL that works with actual wallets"""
        reference = self.generate_reference_key()
        
        # Solana Pay specification URL
        params = {
            'amount': str(amount_sol),
            'reference': reference,
            'label': f"SolClub - {product_name}",
            'message': f"Complete purchase at {store_id} to earn mystery NFTs!",
            'memo': f"SolClub-{store_id}-{reference[:8]}"
        }
        
        # Create proper Solana Pay URL
        base_url = f"solana:{self.merchant_wallet}"
        query_string = urlencode(params)
        solana_pay_url = f"{base_url}?{query_string}"
        
        return solana_pay_url, reference
    
    def create_solana_pay_request_url(self, amount_sol=0.01, store_id="store_001", product_name="Loyalty Purchase"):
        """Create Solana Pay transaction request URL"""
        reference = self.generate_reference_key()
        
        # Transaction request endpoint URL
        params = {
            'recipient': str(self.merchant_wallet),
            'amount': str(amount_sol),
            'reference': reference,
            'label': f"SolClub - {product_name}",
            'message': f"Purchase at {store_id} - Earn NFT rewards!",
            'store_id': store_id
        }
        
        query_string = urlencode(params)
        request_url = f"{self.backend_url}/solana-pay-request?{query_string}"
        
        return request_url, reference
    
    def create_backend_url(self, user_wallet, store_id="store_001"):
        """Create a backend transaction request URL"""
        reference = self.generate_reference_key()
        
        backend_url = f"{self.backend_url}/transaction-request?user_wallet={user_wallet}&store_id={store_id}&reference={reference}"
        
        return backend_url, reference
    
    def generate_qr_code(self, url, filename=None, qr_type="backend"):
        """Generate QR code and save to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"solclub_qr_{qr_type}_{timestamp}.png"
        
        # Create QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save image
        filepath = os.path.join(self.output_dir, filename)
        img.save(filepath)
        
        print(f"✅ QR Code saved: {filepath}")
        return filepath
    
    def save_transaction_metadata(self, reference, url, qr_type, user_wallet=None, store_id=None):
        """Save transaction metadata for tracking"""
        metadata = {
            "reference": reference,
            "url": url,
            "qr_type": qr_type,
            "user_wallet": user_wallet,
            "store_id": store_id,
            "timestamp": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Load existing metadata
        metadata_file = os.path.join(self.output_dir, "transaction_metadata.json")
        all_metadata = []
        
        if os.path.exists(metadata_file):
            with open(metadata_file, 'r') as f:
                all_metadata = json.load(f)
        
        all_metadata.append(metadata)
        
        # Save updated metadata
        with open(metadata_file, 'w') as f:
            json.dump(all_metadata, f, indent=2)
        
        print(f"📝 Metadata saved for reference: {reference}")
        return metadata

async def main():
    print("🎯 REAL SolClub Solana Pay QR Generator")
    print("=" * 60)
    
    # Initialize real Solana Pay generator
    generator = SolanaPayQRGenerator()
    
    # Fund merchant wallet for testing
    print("\n💰 Setting up merchant wallet...")
    await generator.fund_merchant_wallet(2.0)
    
    # Generate different types of purchase QR codes
    purchase_scenarios = [
        {"amount": 0.01, "store": "coffee_shop", "product": "Coffee Purchase"},
        {"amount": 0.05, "store": "retail_store", "product": "Retail Purchase"},
        {"amount": 0.1, "store": "premium_store", "product": "Premium Purchase"}
    ]
    
    generated_qrs = []
    
    for scenario in purchase_scenarios:
        print(f"\n🏪 Generating QR for {scenario['product']}...")
        
        # Generate REAL Solana Pay URL
        solana_url, reference = generator.create_solana_pay_url(
            amount_sol=scenario['amount'],
            store_id=scenario['store'],
            product_name=scenario['product']
        )
        
        print(f"💳 Amount: {scenario['amount']} SOL")
        print(f"🔗 Solana Pay URL: {solana_url}")
        
        # Generate QR code
        qr_filename = f"solana_pay_{scenario['store']}_{scenario['amount']}.png"
        qr_path = generator.generate_qr_code(solana_url, qr_filename, "solana_pay")
        
        # Save metadata
        metadata = {
            "reference": reference,
            "url": solana_url,
            "amount_sol": scenario['amount'],
            "store_id": scenario['store'],
            "product_name": scenario['product'],
            "merchant_wallet": str(generator.merchant_wallet),
            "created_at": datetime.now().isoformat(),
            "qr_path": qr_path,
            "status": "active"
        }
        
        generator.save_transaction_metadata(
            reference, 
            solana_url, 
            "solana_pay",
            store_id=scenario['store']
        )
        
        generated_qrs.append(metadata)
        print(f"✅ QR saved: {qr_path}")
    
    # Generate transaction request URLs for complex flows
    print(f"\n🌐 Generating Transaction Request URLs...")
    for scenario in purchase_scenarios[:2]:  # Just first 2 for demo
        request_url, reference = generator.create_solana_pay_request_url(
            amount_sol=scenario['amount'],
            store_id=scenario['store'],
            product_name=scenario['product']
        )
        
        qr_filename = f"solana_pay_request_{scenario['store']}.png"
        qr_path = generator.generate_qr_code(request_url, qr_filename, "transaction_request")
        
        print(f"🔗 Request URL: {request_url}")
        print(f"✅ Request QR: {qr_path}")
    
    # Display final summary
    print("\n" + "=" * 60)
    print("🎉 REAL Solana Pay QR Codes Generated!")
    print("=" * 60)
    
    print(f"\n🏪 Merchant Wallet: {generator.merchant_wallet}")
    print(f"💰 Total QR codes generated: {len(generated_qrs)}")
    
    print(f"\n📱 How to test:")
    print(f"1. Open Phantom or Solflare wallet on mobile")
    print(f"2. Scan any generated QR code")
    print(f"3. Approve the transaction")
    print(f"4. Transaction will be processed on Solana devnet")
    print(f"5. Backend will detect payment and mint NFT rewards")
    
    print(f"\n💡 QR Code Files:")
    for qr_data in generated_qrs:
        print(f"   • {qr_data['product']}: {qr_data['qr_path']}")
    
    await generator.client.close()

if __name__ == "__main__":
    asyncio.run(main())