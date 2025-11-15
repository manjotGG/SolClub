"""
QR Code Display Utility
Simple utility to view generated QR codes
"""

import os
from PIL import Image
import json

def display_qr_info():
    """Display information about generated QR codes"""
    data_dir = "../data"
    metadata_file = os.path.join(data_dir, "transaction_metadata.json")
    
    if not os.path.exists(metadata_file):
        print("❌ No transaction metadata found. Generate QR codes first.")
        return
    
    with open(metadata_file, 'r') as f:
        metadata = json.load(f)
    
    print("🔍 Generated QR Codes:")
    print("=" * 60)
    
    for i, item in enumerate(metadata, 1):
        print(f"\n{i}. Reference: {item['reference']}")
        print(f"   Type: {item['qr_type']}")
        print(f"   URL: {item['url']}")
        print(f"   Timestamp: {item['timestamp']}")
        print(f"   Status: {item['status']}")
        if item.get('user_wallet'):
            print(f"   User Wallet: {item['user_wallet']}")
        if item.get('store_id'):
            print(f"   Store ID: {item['store_id']}")

def list_qr_files():
    """List all QR code files"""
    data_dir = "../data"
    
    if not os.path.exists(data_dir):
        print("❌ Data directory not found.")
        return
    
    qr_files = [f for f in os.listdir(data_dir) if f.endswith('.png')]
    
    if not qr_files:
        print("❌ No QR code files found.")
        return
    
    print("\n📁 QR Code Files:")
    print("=" * 40)
    
    for i, filename in enumerate(qr_files, 1):
        filepath = os.path.join(data_dir, filename)
        file_size = os.path.getsize(filepath)
        print(f"{i}. {filename} ({file_size} bytes)")

if __name__ == "__main__":
    display_qr_info()
    list_qr_files()