import sqlite3
from pathlib import Path
import json

DB_PATH = Path(__file__).resolve().parents[1] / "solclub.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS merchants (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                wallet_address TEXT NOT NULL,
                api_key TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS customers (
                wallet TEXT PRIMARY KEY,
                total_points INTEGER NOT NULL DEFAULT 0,
                tier TEXT NOT NULL DEFAULT 'Silver'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                merchant_id INTEGER NOT NULL,
                amount REAL NOT NULL,
                signature TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchants (id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS nft_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                nft_type TEXT NOT NULL,
                mint_address TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS merchant_profiles (
                id INTEGER PRIMARY KEY,
                name TEXT,
                cashback_pool_percentage REAL NOT NULL DEFAULT 2.0,
                max_cashback_limit REAL NOT NULL DEFAULT 0.05,
                weekly_distribution_rules TEXT NOT NULL DEFAULT '{"base_rate": 0.01, "tiers": [{"min_transactions": 3, "rate": 0.02}, {"min_transactions": 5, "rate": 0.03}, {"min_transactions": 10, "rate": 0.05}]}'
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cashback_rewards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet TEXT NOT NULL,
                merchant_id INTEGER NOT NULL,
                transaction_signature TEXT NOT NULL UNIQUE,
                transaction_amount REAL NOT NULL,
                cashback_amount REAL NOT NULL,
                reward_tier TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchant_profiles (id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_wallet TEXT NOT NULL,
                network TEXT NOT NULL DEFAULT 'testnet',
                wallet_provider TEXT,
                is_primary INTEGER NOT NULL DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS franchises (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id INTEGER NOT NULL,
                franchise_name TEXT NOT NULL,
                location TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (merchant_id) REFERENCES merchant_profiles (id)
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS loyalty_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tier_name TEXT NOT NULL UNIQUE,
                min_weekly_transactions INTEGER NOT NULL,
                cashback_rate REAL NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # Seed defaults so new modules can run without manual setup.
        cur.execute(
            """
            INSERT OR IGNORE INTO merchant_profiles (id, name)
            VALUES (1, 'Default Merchant')
            """
        )
        cur.execute(
            """
            INSERT OR IGNORE INTO loyalty_tiers (tier_name, min_weekly_transactions, cashback_rate)
            VALUES
                ('Bronze', 0, 0.01),
                ('Silver', 3, 0.02),
                ('Gold', 5, 0.03),
                ('Platinum', 10, 0.05)
            """
        )
    return True


def get_merchant_profile(merchant_id: int):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, name, cashback_pool_percentage, max_cashback_limit, weekly_distribution_rules
            FROM merchant_profiles
            WHERE id = ?
            """,
            (merchant_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return {
            "id": row[0],
            "name": row[1],
            "cashback_pool_percentage": row[2],
            "max_cashback_limit": row[3],
            "weekly_distribution_rules": json.loads(row[4] or "{}"),
        }


def upsert_merchant_profile(
    merchant_id: int,
    name: str,
    cashback_pool_percentage: float,
    max_cashback_limit: float,
    weekly_distribution_rules: dict,
):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO merchant_profiles (
                id, name, cashback_pool_percentage, max_cashback_limit, weekly_distribution_rules
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                cashback_pool_percentage = excluded.cashback_pool_percentage,
                max_cashback_limit = excluded.max_cashback_limit,
                weekly_distribution_rules = excluded.weekly_distribution_rules
            """,
            (
                merchant_id,
                name,
                cashback_pool_percentage,
                max_cashback_limit,
                json.dumps(weekly_distribution_rules),
            ),
        )
        conn.commit()


def save_cashback_reward(
    wallet: str,
    merchant_id: int,
    transaction_signature: str,
    transaction_amount: float,
    cashback_amount: float,
    reward_tier: str,
):
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT OR IGNORE INTO cashback_rewards (
                wallet, merchant_id, transaction_signature, transaction_amount, cashback_amount, reward_tier
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                wallet,
                merchant_id,
                transaction_signature,
                transaction_amount,
                cashback_amount,
                reward_tier,
            ),
        )
        conn.commit()

