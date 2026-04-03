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

from database.db import get_connection, get_merchant_profile

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))
DATA_DIR = os.path.abspath(os.path.join(PROJECT_ROOT, "data"))
os.makedirs(DATA_DIR, exist_ok=True)

@dataclass
class LoyaltyRule:
    """Represents a loyalty program rule"""
    trigger_count: int
    reward_type: str
    reward_name: str
    reward_description: str
    is_recurring: bool = False
    cooldown_days: int = 0


@dataclass
class CashbackDecision:
    wallet: str
    merchant_id: int
    weekly_transaction_count: int
    reward_tier: str
    cashback_rate: float
    cashback_amount: float
    nft_rarity: str

class LoyaltyRulesEngine:
    def __init__(self, db_path=os.path.join(DATA_DIR, "loyalty.db"), use_sqlite=True):
        self.db_path = db_path
        self.use_sqlite = use_sqlite
        self.json_file = os.path.join(DATA_DIR, "loyalty_data.json")
        
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
        # standard tier thresholds for loyalty program
        if transaction_count >= 20:
            return "platinum"
        elif transaction_count >= 10:
            return "gold"
        elif transaction_count >= 5:
            return "silver"
        else:
            return "bronze"

    def get_nft_rarity(self, transaction_count: int) -> str:
        """Compute NFT rarity with increasing chances for higher rarity as activity grows"""
        import random

        base = {
            "common_mystery": 70,
            "rare_mystery": 20,
            "epic_mystery": 8,
            "legendary_mystery": 2,
        }

        # increase per-5-tx boosts (cumulative)
        boost_steps = transaction_count // 5
        rare_bonus = 5 * boost_steps
        epic_bonus = 2 * boost_steps
        legend_bonus = 1 * boost_steps

        # apply caps to keep inside 100
        rare = min(base["rare_mystery"] + rare_bonus, 60)
        epic = min(base["epic_mystery"] + epic_bonus, 25)
        legendary = min(base["legendary_mystery"] + legend_bonus, 10)

        common = max(100 - (rare + epic + legendary), 0)

        weights = [common, rare, epic, legendary]
        rarities = ["common_mystery", "rare_mystery", "epic_mystery", "legendary_mystery"]

        rarity = random.choices(rarities, weights=weights, k=1)[0]
        return rarity

    def evaluate_cashback_and_nft(
        self,
        wallet: str,
        merchant_id: int,
        transaction_amount: float,
        now: Optional[datetime] = None,
    ) -> CashbackDecision:
        """Centralized reward decision: cashback amount + tier + NFT rarity."""
        now = now or datetime.utcnow()
        normalized_wallet = wallet.strip()

        weekly_count = self._weekly_transaction_count_central(normalized_wallet, now)
        weekly_revenue = self._weekly_revenue_central(merchant_id, now)

        profile = get_merchant_profile(merchant_id) or get_merchant_profile(1) or {}
        rules = profile.get("weekly_distribution_rules", {})
        base_rate = float(rules.get("base_rate", 0.01))
        tiers = rules.get(
            "tiers",
            [
                {"min_transactions": 3, "rate": 0.02},
                {"min_transactions": 5, "rate": 0.03},
                {"min_transactions": 10, "rate": 0.05},
            ],
        )

        cashback_rate = self._resolve_cashback_rate(base_rate, tiers, weekly_count)
        reward_tier = self._tier_from_cashback_rate(cashback_rate)

        pool_pct = float(profile.get("cashback_pool_percentage", 2.0)) / 100.0
        max_cashback_limit = float(profile.get("max_cashback_limit", 0.05))
        pool_balance = max(weekly_revenue * pool_pct, 0.0)

        projected_cashback = transaction_amount * cashback_rate
        cashback_amount = min(projected_cashback, max_cashback_limit, pool_balance)
        cashback_amount = max(round(cashback_amount, 6), 0.0)

        nft_rarity = self.get_nft_rarity(max(weekly_count, 1))

        return CashbackDecision(
            wallet=normalized_wallet,
            merchant_id=merchant_id,
            weekly_transaction_count=weekly_count,
            reward_tier=reward_tier,
            cashback_rate=cashback_rate,
            cashback_amount=cashback_amount,
            nft_rarity=nft_rarity,
        )

    def _weekly_transaction_count_central(self, wallet: str, now: datetime) -> int:
        start = (now - timedelta(days=7)).isoformat()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COUNT(*)
                FROM transactions
                WHERE wallet = ? AND created_at >= ?
                """,
                (wallet, start),
            )
            row = cur.fetchone()
            return int(row[0] if row else 0)

    def _weekly_revenue_central(self, merchant_id: int, now: datetime) -> float:
        start = (now - timedelta(days=7)).isoformat()
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT COALESCE(SUM(amount), 0)
                FROM transactions
                WHERE merchant_id = ? AND created_at >= ?
                """,
                (merchant_id, start),
            )
            row = cur.fetchone()
            return float(row[0] if row else 0.0)

    def _resolve_cashback_rate(self, base_rate: float, tiers: List[Dict[str, Any]], weekly_count: int) -> float:
        chosen_rate = base_rate
        for tier in tiers:
            if weekly_count >= int(tier.get("min_transactions", 0)):
                chosen_rate = max(chosen_rate, float(tier.get("rate", base_rate)))
        return chosen_rate

    def _tier_from_cashback_rate(self, rate: float) -> str:
        if rate >= 0.05:
            return "Platinum"
        if rate >= 0.03:
            return "Gold"
        if rate >= 0.02:
            return "Silver"
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


def get_nft_rarity(transaction_count: int) -> str:
    """Module-level helper for determining NFT rarity based on transaction count."""
    engine = LoyaltyRulesEngine(use_sqlite=False)
    return engine.get_nft_rarity(transaction_count)


def get_reward_decision(wallet: str, merchant_id: int, transaction_amount: float) -> CashbackDecision:
    """Module-level helper to get a centralized cashback + NFT decision."""
    engine = LoyaltyRulesEngine(use_sqlite=False)
    return engine.evaluate_cashback_and_nft(wallet, merchant_id, transaction_amount)


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