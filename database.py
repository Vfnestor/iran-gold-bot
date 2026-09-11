import sqlite3
from datetime import datetime, timezone


DB_PATH = "data/gold.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_prices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            price INTEGER NOT NULL,
            currency TEXT NOT NULL,
            source TEXT NOT NULL,
            timestamp TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def save_price(data):
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    timestamp = data.get("timestamp")

    if not timestamp:
        timestamp = datetime.now(timezone.utc).isoformat()

    cursor.execute("""
        INSERT INTO gold_prices (
            symbol,
            price,
            currency,
            source,
            timestamp
        )
        VALUES (?, ?, ?, ?, ?)
    """, (
        data["symbol"],
        data["price"],
        data["currency"],
        data["source"],
        timestamp
    ))

    conn.commit()
    conn.close()


def get_latest_prices(limit=10):
    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            price,
            currency,
            source,
            timestamp
        FROM gold_prices
        ORDER BY id DESC
        LIMIT ?
    """, (limit,))

    rows = cursor.fetchall()

    conn.close()

    return rows
