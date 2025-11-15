"""
NFT Gallery Viewer
View and manage minted loyalty NFTs
"""

import json
import os
from datetime import datetime
from typing import List, Dict, Any

class NFTGallery:
    def __init__(self):
        self.nft_file = "../data/nft_records.json"
        self.metadata_dir = "../data/nft_metadata"
    
    def load_nft_records(self) -> List[Dict[str, Any]]:
        """Load all NFT records"""
        if not os.path.exists(self.nft_file):
            return []
        
        with open(self.nft_file, 'r') as f:
            return json.load(f)
    
    def display_nft_gallery(self):
        """Display all minted NFTs"""
        records = self.load_nft_records()
        
        if not records:
            print("📭 No NFTs minted yet.")
            return
        
        print("🎨 SolClub NFT Gallery")
        print("=" * 60)
        
        # Group by type
        nft_types = {}
        for record in records:
            nft_type = record["nft_type"]
            if nft_type not in nft_types:
                nft_types[nft_type] = []
            nft_types[nft_type].append(record)
        
        for nft_type, nfts in nft_types.items():
            print(f"\n🏷️  {nft_type.upper().replace('_', ' ')}")
            print("-" * 40)
            
            for i, nft in enumerate(nfts, 1):
                print(f"   {i}. Mint: {nft['mint_address'][:12]}...")
                print(f"      Owner: {nft['owner'][:12]}...")
                print(f"      Minted: {nft['minted_at'][:10]}")
                print(f"      Transactions: {nft['transaction_count']}")
                print()
    
    def display_user_nfts(self, user_wallet: str):
        """Display NFTs for a specific user"""
        records = self.load_nft_records()
        user_nfts = [record for record in records if record["owner"] == user_wallet]
        
        if not user_nfts:
            print(f"📭 No NFTs found for wallet: {user_wallet}")
            return
        
        print(f"🎨 NFTs for {user_wallet}")
        print("=" * 60)
        
        for i, nft in enumerate(user_nfts, 1):
            print(f"\n{i}. {nft['nft_type'].replace('_', ' ').title()}")
            print(f"   Mint Address: {nft['mint_address']}")
            print(f"   Minted: {nft['minted_at']}")
            print(f"   Transaction Count: {nft['transaction_count']}")
            print(f"   Metadata URI: {nft['metadata_uri']}")
    
    def get_nft_statistics(self):
        """Get NFT minting statistics"""
        records = self.load_nft_records()
        
        if not records:
            return {"total": 0}
        
        stats = {
            "total_nfts": len(records),
            "unique_owners": len(set(record["owner"] for record in records)),
            "nft_types": {},
            "recent_mints": []
        }
        
        # Count by type
        for record in records:
            nft_type = record["nft_type"]
            stats["nft_types"][nft_type] = stats["nft_types"].get(nft_type, 0) + 1
        
        # Get recent mints (last 10)
        sorted_records = sorted(records, key=lambda x: x["minted_at"], reverse=True)
        stats["recent_mints"] = sorted_records[:10]
        
        return stats
    
    def display_statistics(self):
        """Display NFT statistics"""
        stats = self.get_nft_statistics()
        
        if stats["total_nfts"] == 0:
            print("📊 No NFT statistics available yet.")
            return
        
        print("📊 SolClub NFT Statistics")
        print("=" * 50)
        
        print(f"🎯 Total NFTs Minted: {stats['total_nfts']}")
        print(f"👥 Unique Owners: {stats['unique_owners']}")
        
        print("\n🏷️ NFTs by Type:")
        for nft_type, count in stats["nft_types"].items():
            print(f"   {nft_type.replace('_', ' ').title()}: {count}")
        
        print("\n🕒 Recent Mints:")
        for i, nft in enumerate(stats["recent_mints"][:5], 1):
            minted_date = nft["minted_at"][:10]
            print(f"   {i}. {nft['nft_type'].replace('_', ' ').title()} - {minted_date}")
    
    def search_nfts(self, search_term: str):
        """Search NFTs by various criteria"""
        records = self.load_nft_records()
        results = []
        
        search_term = search_term.lower()
        
        for record in records:
            # Search in various fields
            if (search_term in record["nft_type"].lower() or
                search_term in record["owner"].lower() or
                search_term in record["mint_address"].lower()):
                results.append(record)
        
        if not results:
            print(f"🔍 No NFTs found matching: {search_term}")
            return
        
        print(f"🔍 Search Results for '{search_term}':")
        print("=" * 50)
        
        for i, nft in enumerate(results, 1):
            print(f"\n{i}. {nft['nft_type'].replace('_', ' ').title()}")
            print(f"   Owner: {nft['owner'][:16]}...")
            print(f"   Mint: {nft['mint_address'][:16]}...")
            print(f"   Minted: {nft['minted_at'][:10]}")

def main():
    """Interactive NFT gallery"""
    gallery = NFTGallery()
    
    while True:
        print("\n🎨 SolClub NFT Gallery")
        print("=" * 40)
        print("1. View all NFTs")
        print("2. View user NFTs")
        print("3. View statistics")
        print("4. Search NFTs")
        print("5. Exit")
        
        choice = input("\nSelect option (1-5): ").strip()
        
        if choice == "1":
            gallery.display_nft_gallery()
        
        elif choice == "2":
            wallet = input("Enter wallet address: ").strip()
            gallery.display_user_nfts(wallet)
        
        elif choice == "3":
            gallery.display_statistics()
        
        elif choice == "4":
            term = input("Enter search term: ").strip()
            gallery.search_nfts(term)
        
        elif choice == "5":
            print("👋 Goodbye!")
            break
        
        else:
            print("❌ Invalid option. Please try again.")

if __name__ == "__main__":
    main()