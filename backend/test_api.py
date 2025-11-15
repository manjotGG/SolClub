"""
Backend API Testing Client
Test the FastAPI backend endpoints
"""

import requests
import json
import time
from datetime import datetime

class BackendTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
    
    def test_connection(self):
        """Test basic connection to the API"""
        try:
            response = requests.get(f"{self.base_url}/")
            if response.status_code == 200:
                print("✅ Backend connection successful")
                print(f"📋 API Info: {response.json()}")
                return True
            else:
                print(f"❌ Connection failed: {response.status_code}")
                return False
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return False
    
    def test_transaction_request(self, user_wallet, store_id, reference):
        """Test transaction request endpoint"""
        try:
            params = {
                "user_wallet": user_wallet,
                "store_id": store_id,
                "reference": reference
            }
            
            response = requests.get(f"{self.base_url}/transaction-request", params=params)
            
            if response.status_code == 200:
                print("✅ Transaction request successful")
                print(f"📋 Response: {json.dumps(response.json(), indent=2)}")
                return response.json()
            else:
                print(f"❌ Transaction request failed: {response.status_code}")
                print(f"📋 Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Transaction request error: {e}")
            return None
    
    def test_validate_transaction(self, reference, signature=None):
        """Test transaction validation"""
        try:
            data = {"reference": reference}
            if signature:
                data["signature"] = signature
            
            response = requests.post(f"{self.base_url}/validate", json=data)
            
            if response.status_code == 200:
                print("✅ Transaction validation successful")
                print(f"📋 Response: {json.dumps(response.json(), indent=2)}")
                return response.json()
            else:
                print(f"❌ Transaction validation failed: {response.status_code}")
                print(f"📋 Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Transaction validation error: {e}")
            return None
    
    def test_reward_processing(self, user_wallet, store_id, transaction_signature):
        """Test reward processing"""
        try:
            data = {
                "user_wallet": user_wallet,
                "store_id": store_id,
                "transaction_signature": transaction_signature
            }
            
            response = requests.post(f"{self.base_url}/reward", json=data)
            
            if response.status_code == 200:
                print("✅ Reward processing successful")
                print(f"📋 Response: {json.dumps(response.json(), indent=2)}")
                return response.json()
            else:
                print(f"❌ Reward processing failed: {response.status_code}")
                print(f"📋 Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Reward processing error: {e}")
            return None
    
    def test_user_stats(self, wallet):
        """Test user statistics retrieval"""
        try:
            response = requests.get(f"{self.base_url}/user/{wallet}/stats")
            
            if response.status_code == 200:
                print("✅ User stats retrieved successfully")
                print(f"📋 Response: {json.dumps(response.json(), indent=2)}")
                return response.json()
            else:
                print(f"❌ User stats failed: {response.status_code}")
                print(f"📋 Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ User stats error: {e}")
            return None
    
    def test_admin_stats(self):
        """Test admin statistics"""
        try:
            response = requests.get(f"{self.base_url}/admin/stats")
            
            if response.status_code == 200:
                print("✅ Admin stats retrieved successfully")
                print(f"📋 Response: {json.dumps(response.json(), indent=2)}")
                return response.json()
            else:
                print(f"❌ Admin stats failed: {response.status_code}")
                print(f"📋 Error: {response.text}")
                return None
                
        except Exception as e:
            print(f"❌ Admin stats error: {e}")
            return None

def run_full_test():
    """Run a complete test scenario"""
    print("🧪 SolClub Backend API Testing")
    print("=" * 50)
    
    tester = BackendTester()
    
    # Test data
    test_wallet = "8WzDXbvfdkVeVZV5cRgQzrNyKaEP5qN7nJtfxQG3BqLk"
    test_store = "store_001"
    test_reference = f"test_ref_{int(time.time())}"
    test_signature = f"test_sig_{int(time.time())}"
    
    # Test 1: Connection
    print("\n1️⃣ Testing connection...")
    if not tester.test_connection():
        print("❌ Cannot continue without backend connection")
        return
    
    # Test 2: Transaction Request
    print("\n2️⃣ Testing transaction request...")
    tx_response = tester.test_transaction_request(test_wallet, test_store, test_reference)
    
    # Test 3: Validation (without signature)
    print("\n3️⃣ Testing validation without signature...")
    tester.test_validate_transaction(test_reference)
    
    # Test 4: Validation (with signature)
    print("\n4️⃣ Testing validation with signature...")
    tester.test_validate_transaction(test_reference, test_signature)
    
    # Test 5: Reward Processing
    print("\n5️⃣ Testing reward processing...")
    tester.test_reward_processing(test_wallet, test_store, test_signature)
    
    # Test 6: User Stats
    print("\n6️⃣ Testing user stats...")
    tester.test_user_stats(test_wallet)
    
    # Test 7: Admin Stats
    print("\n7️⃣ Testing admin stats...")
    tester.test_admin_stats()
    
    print("\n🎉 Testing completed!")

if __name__ == "__main__":
    run_full_test()