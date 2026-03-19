import sqlite3
from pathlib import Path

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
    return True

