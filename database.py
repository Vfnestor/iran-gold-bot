import os
import sqlite3
from datetime import datetime, timezone


DB_DIR = "data"
DB_PATH = os.path.join(DB_DIR, "gold.db")


# ==========================================
# Database Connection
# ==========================================

def get_connection():

    os.makedirs(
        DB_DIR,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    return conn


# ==========================================
# Initialize Database
# ==========================================

def init_db():

    conn = get_connection()

    cursor = conn.cursor()

    # ======================================
    # Raw Gold Prices
    # ======================================

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

    # ======================================
    # Candles
    # ======================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gold_candles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            symbol TEXT NOT NULL,

            timeframe TEXT NOT NULL,

            timestamp TEXT NOT NULL,

            open INTEGER NOT NULL,
            high INTEGER NOT NULL,
            low INTEGER NOT NULL,
            close INTEGER NOT NULL,

            volume INTEGER DEFAULT 0,

            created_at TEXT NOT NULL,

            UNIQUE(
                symbol,
                timeframe,
                timestamp
            )
        )
    """)

    # ======================================
    # Indexes
    # ======================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_gold_prices_timestamp
        ON gold_prices(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_gold_prices_source
        ON gold_prices(source)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_gold_candles_timeframe
        ON gold_candles(timeframe)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_gold_candles_timestamp
        ON gold_candles(timestamp)
    """)

    conn.commit()

    conn.close()

    print(
        f"🗄️ Database initialized: {DB_PATH}"
    )


# ==========================================
# Save Raw Price
# ==========================================

def save_price(data):

    timestamp = data.get("timestamp")

    if not timestamp:

        timestamp = datetime.now(
            timezone.utc
        ).isoformat()

    conn = get_connection()

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

    conn.close()

    print(
        f"💾 Price saved: "
        f"{data['price']:,} "
        f"{data['currency']}"
    )


# ==========================================
# Get Latest Prices
# ==========================================

def get_latest_prices(
    limit=10
):

    conn = get_connection()

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
    """, (
        limit,
    ))

    rows = cursor.fetchall()

    conn.close()

    print(
        f"📊 History records found: "
        f"{len(rows)}"
    )

    return rows


# ==========================================
# Save Candle
# ==========================================

def save_candle(
    symbol,
    timeframe,
    timestamp,
    open_price,
    high_price,
    low_price,
    close_price,
    volume=0
):

    created_at = datetime.now(
        timezone.utc
    ).isoformat()

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO gold_candles (
            symbol,
            timeframe,
            timestamp,
            open,
            high,
            low,
            close,
            volume,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        symbol,
        timeframe,
        timestamp,
        open_price,
        high_price,
        low_price,
        close_price,
        volume,
        created_at
    ))

    conn.commit()

    conn.close()

    print(
        f"🕯️ Candle saved: "
        f"{symbol} "
        f"{timeframe} "
        f"{timestamp}"
    )


# ==========================================
# Get Candles
# ==========================================

def get_candles(
    symbol="gold_18k",
    timeframe="1m",
    limit=100
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM gold_candles

        WHERE symbol = ?
        AND timeframe = ?

        ORDER BY timestamp DESC

        LIMIT ?
    """, (
        symbol,
        timeframe,
        limit
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ==========================================
# Get Latest Candle
# ==========================================

def get_latest_candle(
    symbol="gold_18k",
    timeframe="1m"
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM gold_candles

        WHERE symbol = ?
        AND timeframe = ?

        ORDER BY timestamp DESC

        LIMIT 1
    """, (
        symbol,
        timeframe
    ))

    row = cursor.fetchone()

    conn.close()

    return row


# ==========================================
# Database Statistics
# ==========================================

def get_database_stats():

    conn = get_connection()

    cursor = conn.cursor()

    # ------------------------------
    # Raw price count
    # ------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM gold_prices
    """)

    raw_price_count = cursor.fetchone()[0]

    # ------------------------------
    # Candle count
    # ------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM gold_candles
    """)

    candle_count = cursor.fetchone()[0]

    # ------------------------------
    # Latest raw price
    # ------------------------------

    cursor.execute("""
        SELECT
            price,
            currency,
            source,
            timestamp
        FROM gold_prices

        ORDER BY id DESC

        LIMIT 1
    """)

    latest_price = cursor.fetchone()

    # ------------------------------
    # Latest candle
    # ------------------------------

    cursor.execute("""
        SELECT
            timestamp,
            open,
            high,
            low,
            close,
            volume
        FROM gold_candles

        WHERE timeframe = '1m'

        ORDER BY timestamp DESC

        LIMIT 1
    """)

    latest_candle = cursor.fetchone()

    conn.close()

    return {
        "raw_price_count": raw_price_count,
        "candle_count": candle_count,
        "latest_price": latest_price,
        "latest_candle": latest_candle,
    }
