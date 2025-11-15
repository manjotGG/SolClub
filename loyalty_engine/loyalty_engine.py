"""
MODULE 4: Loyalty Rules Engine
Manages loyalty program rules, user progression, and reward distribution
"""

import json
import os
import sqlite3
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import asyncio
from dataclasses import dataclass

@dataclass
class LoyaltyRule:
    """Represents a loyalty program rule"""
    trigger_count: int
    reward_type: str
    reward_name: str
    reward_description: str
    is_recurring: bool = False
    cooldown_days: int = 0

class LoyaltyRulesEngine:
    def __init__(self, db_path="../data/loyalty.db", use_sqlite=True):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self.json_file = "../data/loyalty_data.json"
        
        # Create data directory
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        # Initialize database
        if use_sqlite:
            self.init_sqlite_db()
        
        # Define loyalty rules
        self.rules = self.define_loyalty_rules()
    
    def init_sqlite_db(self):
        """Initialize SQLite database with loyalty tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                wallet_address TEXT PRIMARY KEY,
                total_transactions INTEGER DEFAULT 0,
                total_rewards INTEGER DEFAULT 0,
                points_balance INTEGER DEFAULT 0,
                tier TEXT DEFAULT 'Bronze',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Transactions table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT,
                store_id TEXT,
                transaction_signature TEXT,
                amount REAL DEFAULT 0.001,
                reference TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (wallet_address) REFERENCES users (wallet_address)
            )
        ''')
        
        # Rewards table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT,
                reward_type TEXT,
                reward_name TEXT,
                reward_description TEXT,
                transaction_count INTEGER,
                nft_mint_address TEXT,
                earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT DEFAULT 'pending',
                FOREIGN KEY (wallet_address) REFERENCES users (wallet_address)
            )
        ''')
        
        # Loyalty rules table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS loyalty_rules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trigger_count INTEGER,
                reward_type TEXT,
                reward_name TEXT,
                reward_description TEXT,
                is_recurring BOOLEAN DEFAULT FALSE,
                cooldown_days INTEGER DEFAULT 0,
                is_active BOOLEAN DEFAULT TRUE
            )
        ''')
        
        conn.commit()
        conn.close()
        
        print("✅ SQLite database initialized")
    
    def define_loyalty_rules(self) -> List[LoyaltyRule]:
        """Define the loyalty program rules"""
        rules = [
            LoyaltyRule(1, "bronze_nft", "Welcome Bronze", "First purchase NFT badge", False),
            LoyaltyRule(3, "loyalty_points", "Progress Points", "Earned 50 loyalty points", False),
            LoyaltyRule(5, "silver_nft", "Silver Member", "5 purchases milestone NFT", False),
            LoyaltyRule(8, "loyalty_points", "Mid-tier Bonus", "Earned 100 loyalty points", False),
            LoyaltyRule(10, "gold_nft", "Gold Member", "10 purchases milestone NFT", False),
            LoyaltyRule(15, "loyalty_points", "Gold Bonus", "Earned 200 loyalty points", False),
            LoyaltyRule(25, "platinum_nft", "Platinum Champion", "25 purchases champion NFT", False),
            LoyaltyRule(50, "diamond_nft", "Diamond Elite", "50 purchases elite NFT", False),
            LoyaltyRule(100, "legend_nft", "Legend Status", "100 purchases legend NFT", False),
            # Recurring rules
            LoyaltyRule(20, "platinum_nft", "Platinum Recurring", "Every 20 purchases", True),
            LoyaltyRule(10, "loyalty_points", "Points Bonus", "Regular points bonus", True, 7),
        ]
        
        # Save rules to database if using SQLite
        if self.use_sqlite:
            self.save_rules_to_db(rules)
        
        return rules
    
    def save_rules_to_db(self, rules: List[LoyaltyRule]):
        """Save loyalty rules to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Clear existing rules
        cursor.execute("DELETE FROM loyalty_rules")
        
        # Insert new rules
        for rule in rules:
            cursor.execute('''
                INSERT INTO loyalty_rules 
                (trigger_count, reward_type, reward_name, reward_description, is_recurring, cooldown_days)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (rule.trigger_count, rule.reward_type, rule.reward_name, 
                  rule.reward_description, rule.is_recurring, rule.cooldown_days))
        
        conn.commit()
        conn.close()
    
    def get_or_create_user(self, wallet_address: str) -> Dict[str, Any]:
        """Get user data or create new user"""
        if self.use_sqlite:
            return self.get_or_create_user_sqlite(wallet_address)
        else:
            return self.get_or_create_user_json(wallet_address)
    
    def get_or_create_user_sqlite(self, wallet_address: str) -> Dict[str, Any]:
        """Get or create user using SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Try to get existing user
        cursor.execute("SELECT * FROM users WHERE wallet_address = ?", (wallet_address,))
        user = cursor.fetchone()
        
        if user:
            # Convert to dict
            user_data = {
                "wallet_address": user[0],
                "total_transactions": user[1],
                "total_rewards": user[2],
                "points_balance": user[3],
                "tier": user[4],
                "created_at": user[5],
                "last_activity": user[6]
            }
        else:
            # Create new user
            cursor.execute('''
                INSERT INTO users (wallet_address, total_transactions, total_rewards, points_balance, tier)
                VALUES (?, 0, 0, 0, 'Bronze')
            ''', (wallet_address,))
            
            user_data = {
                "wallet_address": wallet_address,
                "total_transactions": 0,
                "total_rewards": 0,
                "points_balance": 0,
                "tier": "Bronze",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat()
            }
        
        conn.commit()
        conn.close()
        return user_data
    
    def get_or_create_user_json(self, wallet_address: str) -> Dict[str, Any]:
        """Get or create user using JSON file"""
        # Load existing data
        if os.path.exists(self.json_file):
            with open(self.json_file, 'r') as f:
                data = json.load(f)
        else:
            data = {"users": {}}
        
        # Get or create user
        if wallet_address not in data["users"]:
            data["users"][wallet_address] = {
                "wallet_address": wallet_address,
                "total_transactions": 0,
                "total_rewards": 0,
                "points_balance": 0,
                "tier": "Bronze",
                "created_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "transaction_history": [],
                "reward_history": []
            }
            
            # Save updated data
            os.makedirs(os.path.dirname(self.json_file), exist_ok=True)
            with open(self.json_file, 'w') as f:
                json.dump(data, f, indent=2)
        
        return data["users"][wallet_address]
    
    def process_transaction(self, wallet_address: str, store_id: str, 
                          transaction_signature: str, amount: float = 0.001) -> Dict[str, Any]:
        """Process a new transaction and determine rewards"""
        
        # Get user data
        user_data = self.get_or_create_user(wallet_address)
        
        # Increment transaction count
        new_transaction_count = user_data["total_transactions"] + 1
        
        # Update user data
        if self.use_sqlite:
            self.update_user_sqlite(wallet_address, {
                "total_transactions": new_transaction_count,
                "last_activity": datetime.now().isoformat()
            })
        else:
            self.update_user_json(wallet_address, {
                "total_transactions": new_transaction_count,
                "last_activity": datetime.now().isoformat()
            })
        
        # Record transaction
        self.record_transaction(wallet_address, store_id, transaction_signature, amount)
        
        # Check for rewards
        earned_rewards = self.check_and_award_rewards(wallet_address, new_transaction_count)
        
        # Update tier
        new_tier = self.calculate_tier(new_transaction_count)
        if new_tier != user_data["tier"]:
            self.update_user_tier(wallet_address, new_tier)
        
        return {
            "wallet_address": wallet_address,
            "transaction_count": new_transaction_count,
            "tier": new_tier,
            "rewards_earned": earned_rewards,
            "next_milestone": self.get_next_milestone(new_transaction_count)
        }
    
    def check_and_award_rewards(self, wallet_address: str, transaction_count: int) -> List[Dict[str, Any]]:
        """Check rules and award appropriate rewards"""
        earned_rewards = []
        
        for rule in self.rules:
            should_award = False
            
            if rule.is_recurring:
                # Recurring rule - check if transaction count is multiple of trigger
                if transaction_count % rule.trigger_count == 0:
                    # Check cooldown for recurring rewards
                    if self.check_cooldown(wallet_address, rule.reward_type, rule.cooldown_days):
                        should_award = True
            else:
                # One-time rule - check exact match
                if transaction_count == rule.trigger_count:
                    should_award = True
            
            if should_award:
                reward = self.award_reward(wallet_address, rule, transaction_count)
                if reward:
                    earned_rewards.append(reward)
        
        return earned_rewards
    
    def award_reward(self, wallet_address: str, rule: LoyaltyRule, transaction_count: int) -> Dict[str, Any]:
        """Award a specific reward to user"""
        reward_data = {
            "wallet_address": wallet_address,
            "reward_type": rule.reward_type,
            "reward_name": rule.reward_name,
            "reward_description": rule.reward_description,
            "transaction_count": transaction_count,
            "earned_at": datetime.now().isoformat(),
            "status": "pending"
        }
        
        # Handle different reward types
        if rule.reward_type.endswith("_nft"):
            # NFT reward - would trigger NFT minting
            reward_data["nft_mint_address"] = f"mock_mint_{int(datetime.now().timestamp())}"
            reward_data["status"] = "nft_pending"
        elif rule.reward_type == "loyalty_points":
            # Points reward
            points_amount = self.calculate_points_reward(transaction_count)
            reward_data["points_amount"] = points_amount
            self.add_points(wallet_address, points_amount)
            reward_data["status"] = "completed"
        
        # Record reward
        self.record_reward(reward_data)
        
        print(f"🎉 Reward awarded: {rule.reward_name} to {wallet_address[:12]}...")
        
        return reward_data
    
    def calculate_points_reward(self, transaction_count: int) -> int:
        """Calculate points reward amount"""
        base_points = 10
        bonus_multiplier = transaction_count // 10
        return base_points + (bonus_multiplier * 5)
    
    def add_points(self, wallet_address: str, points: int):
        """Add points to user balance"""
        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET points_balance = points_balance + ? 
                WHERE wallet_address = ?
            ''', (points, wallet_address))
            conn.commit()
            conn.close()
        else:
            # JSON implementation
            with open(self.json_file, 'r') as f:
                data = json.load(f)
            
            if wallet_address in data["users"]:
                data["users"][wallet_address]["points_balance"] += points
                
                with open(self.json_file, 'w') as f:
                    json.dump(data, f, indent=2)
    
    def calculate_tier(self, transaction_count: int) -> str:
        """Calculate user tier based on transaction count"""
        if transaction_count >= 100:
            return "Legend"
        elif transaction_count >= 50:
            return "Diamond"
        elif transaction_count >= 25:
            return "Platinum"
        elif transaction_count >= 10:
            return "Gold"
        elif transaction_count >= 5:
            return "Silver"
        else:
            return "Bronze"
    
    def get_next_milestone(self, current_count: int) -> Dict[str, Any]:
        """Get next reward milestone"""
        milestones = [1, 5, 10, 25, 50, 100]
        
        for milestone in milestones:
            if current_count < milestone:
                reward_rule = next((rule for rule in self.rules if rule.trigger_count == milestone), None)
                return {
                    "transactions_needed": milestone - current_count,
                    "milestone": milestone,
                    "reward": reward_rule.reward_name if reward_rule else "Special Reward"
                }
        
        # Beyond 100, next milestone is every 25
        next_milestone = ((current_count // 25) + 1) * 25
        return {
            "transactions_needed": next_milestone - current_count,
            "milestone": next_milestone,
            "reward": "Platinum Champion NFT"
        }
    
    def record_transaction(self, wallet_address: str, store_id: str, 
                          transaction_signature: str, amount: float):
        """Record transaction in database"""
        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO transactions 
                (wallet_address, store_id, transaction_signature, amount, status)
                VALUES (?, ?, ?, ?, 'completed')
            ''', (wallet_address, store_id, transaction_signature, amount))
            conn.commit()
            conn.close()
    
    def record_reward(self, reward_data: Dict[str, Any]):
        """Record reward in database"""
        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO rewards 
                (wallet_address, reward_type, reward_name, reward_description, 
                 transaction_count, nft_mint_address, status)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (reward_data["wallet_address"], reward_data["reward_type"],
                  reward_data["reward_name"], reward_data["reward_description"],
                  reward_data["transaction_count"], 
                  reward_data.get("nft_mint_address"), reward_data["status"]))
            conn.commit()
            conn.close()
    
    def update_user_sqlite(self, wallet_address: str, updates: Dict[str, Any]):
        """Update user data in SQLite"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        set_clause = ", ".join(f"{key} = ?" for key in updates.keys())
        values = list(updates.values()) + [wallet_address]
        
        cursor.execute(f"UPDATE users SET {set_clause} WHERE wallet_address = ?", values)
        conn.commit()
        conn.close()
    
    def update_user_json(self, wallet_address: str, updates: Dict[str, Any]):
        """Update user data in JSON"""
        with open(self.json_file, 'r') as f:
            data = json.load(f)
        
        if wallet_address in data["users"]:
            data["users"][wallet_address].update(updates)
            
            with open(self.json_file, 'w') as f:
                json.dump(data, f, indent=2)
    
    def update_user_tier(self, wallet_address: str, new_tier: str):
        """Update user tier"""
        if self.use_sqlite:
            self.update_user_sqlite(wallet_address, {"tier": new_tier})
        else:
            self.update_user_json(wallet_address, {"tier": new_tier})
        
        print(f"🏆 {wallet_address[:12]}... promoted to {new_tier} tier!")
    
    def check_cooldown(self, wallet_address: str, reward_type: str, cooldown_days: int) -> bool:
        """Check if reward is on cooldown"""
        if cooldown_days == 0:
            return True
        
        # Implementation would check last reward of this type
        # For now, return True (no cooldown check)
        return True
    
    def get_user_stats(self, wallet_address: str) -> Dict[str, Any]:
        """Get comprehensive user statistics"""
        user_data = self.get_or_create_user(wallet_address)
        
        if self.use_sqlite:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Get rewards
            cursor.execute('''
                SELECT reward_type, reward_name, earned_at, status 
                FROM rewards WHERE wallet_address = ? 
                ORDER BY earned_at DESC
            ''', (wallet_address,))
            rewards = cursor.fetchall()
            
            # Get recent transactions
            cursor.execute('''
                SELECT store_id, transaction_signature, created_at 
                FROM transactions WHERE wallet_address = ? 
                ORDER BY created_at DESC LIMIT 10
            ''', (wallet_address,))
            transactions = cursor.fetchall()
            
            conn.close()
            
            user_data["rewards_history"] = [
                {"type": r[0], "name": r[1], "earned_at": r[2], "status": r[3]} 
                for r in rewards
            ]
            user_data["recent_transactions"] = [
                {"store_id": t[0], "signature": t[1], "created_at": t[2]} 
                for t in transactions
            ]
        
        return user_data

def test_loyalty_engine():
    """Test the loyalty rules engine"""
    print("🎯 Testing SolClub Loyalty Rules Engine")
    print("=" * 60)
    
    # Initialize engine
    engine = LoyaltyRulesEngine(use_sqlite=True)
    
    # Test wallet
    test_wallet = "8WzDXbvfdkVeVZV5cRgQzrNyKaEP5qN7nJtfxQG3BqLk"
    
    # Simulate transactions
    print(f"\n👤 Testing with wallet: {test_wallet[:16]}...")
    
    # Transaction 1 - Should get Bronze NFT
    print("\n🔄 Processing transaction 1...")
    result1 = engine.process_transaction(test_wallet, "store_001", "tx_sig_1")
    print(f"   Rewards: {len(result1['rewards_earned'])}")
    for reward in result1['rewards_earned']:
        print(f"   ✨ {reward['reward_name']}: {reward['reward_description']}")
    
    # Transaction 5 - Should get Silver NFT
    print("\n🔄 Processing transactions 2-5...")
    for i in range(2, 6):
        result = engine.process_transaction(test_wallet, "store_001", f"tx_sig_{i}")
        if result['rewards_earned']:
            print(f"   Transaction {i} rewards:")
            for reward in result['rewards_earned']:
                print(f"   ✨ {reward['reward_name']}: {reward['reward_description']}")
    
    # Transaction 10 - Should get Gold NFT
    print("\n🔄 Processing transactions 6-10...")
    for i in range(6, 11):
        result = engine.process_transaction(test_wallet, "store_001", f"tx_sig_{i}")
        if result['rewards_earned']:
            print(f"   Transaction {i} rewards:")
            for reward in result['rewards_earned']:
                print(f"   ✨ {reward['reward_name']}: {reward['reward_description']}")
    
    # Get final user stats
    print(f"\n📊 Final user stats:")
    stats = engine.get_user_stats(test_wallet)
    print(f"   Total Transactions: {stats['total_transactions']}")
    print(f"   Total Rewards: {stats['total_rewards']}")
    print(f"   Points Balance: {stats['points_balance']}")
    print(f"   Current Tier: {stats['tier']}")
    
    if 'rewards_history' in stats:
        print(f"   Rewards Earned: {len(stats['rewards_history'])}")
        for reward in stats['rewards_history'][:5]:
            print(f"     • {reward['name']} ({reward['type']})")

if __name__ == "__main__":
    test_loyalty_engine()