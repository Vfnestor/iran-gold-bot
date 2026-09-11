import os
import sqlite3
from datetime import datetime, timezone


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "gold.db")


def init_db():
    # اطمینان از وجود پوشه data
    os.makedirs(DB_DIR, exist_ok=True)

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

    print(f"🗄️ Database initialized: {DB_PATH}")


def save_price(data):
    # اطمینان از وجود پوشه data
    os.makedirs(DB_DIR, exist_ok=True)

    timestamp = data.get("timestamp")

    if not timestamp:
        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    conn = sqlite3.connect(DB_PATH)

    cursor = conn.cursor()

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

    print(
        f"💾 Price saved: "
        f"{data['price']} {data['currency']}"
    )

    conn.close()


def get_latest_prices(limit=10):
    os.makedirs(DB_DIR, exist_ok=True)

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

    print(
        f"📊 History records found: {len(rows)}"
    )

    return rows
