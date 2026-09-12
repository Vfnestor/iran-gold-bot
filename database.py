import os
import sqlite3
from datetime import datetime, timezone


# ============================================================
# DATABASE CONFIG
# ============================================================

DB_DIR = "data"

DB_PATH = os.path.join(
    DB_DIR,
    "gold.db"
)


# ============================================================
# SERVIX QUOTA CONFIG
# ============================================================

# Servix اجازه 50 درخواست روزانه می‌دهد.
# ما عمداً فقط 45 درخواست را استفاده می‌کنیم
# تا 5 درخواست ذخیره اضطراری داشته باشیم.
SERVIX_DAILY_LIMIT = 45


# ============================================================
# CONNECTION
# ============================================================

def get_connection():

    os.makedirs(
        DB_DIR,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DB_PATH
    )

    return conn


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

def init_db():

    conn = get_connection()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # RAW GOLD PRICES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # GOLD CANDLES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # SERVIX DAILY QUOTA
    # --------------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servix_usage (

            usage_date TEXT PRIMARY KEY,

            request_count INTEGER NOT NULL DEFAULT 0,

            updated_at TEXT NOT NULL
        )
    """)

    # --------------------------------------------------------
    # INDEXES
    # --------------------------------------------------------

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
        idx_gold_prices_symbol

        ON gold_prices(symbol)
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

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_gold_candles_symbol

        ON gold_candles(symbol)
    """)

    conn.commit()

    conn.close()

    print(
        f"🗄️ Database initialized: {DB_PATH}",
        flush=True
    )


# ============================================================
# CURRENT UTC DATE
# ============================================================

def get_current_utc_date():

    return datetime.now(
        timezone.utc
    ).date().isoformat()


# ============================================================
# RESERVE SERVIX REQUEST
# ============================================================

def reserve_servix_request(
    daily_limit=SERVIX_DAILY_LIMIT
):
    """
    رزرو یک درخواست Servix.

    این تابع قبل از ارسال HTTP request فراخوانی می‌شود.

    اگر سهمیه موجود باشد:

        True

    اگر سهمیه تمام شده باشد:

        False

    خروجی:

    {
        "allowed": True/False,
        "used": int,
        "remaining": int,
        "date": str
    }

    نکته:
    تراکنش به صورت IMMEDIATE انجام می‌شود تا
    دو درخواست همزمان نتوانند یک سهمیه را دوبار مصرف کنند.
    """

    usage_date = get_current_utc_date()

    conn = get_connection()

    try:

        cursor = conn.cursor()

        # ----------------------------------------------------
        # شروع تراکنش قفل‌شده
        # ----------------------------------------------------

        conn.execute(
            "BEGIN IMMEDIATE"
        )

        # ----------------------------------------------------
        # دریافت مصرف امروز
        # ----------------------------------------------------

        cursor.execute("""
            SELECT request_count

            FROM servix_usage

            WHERE usage_date = ?
        """, (
            usage_date,
        ))

        row = cursor.fetchone()

        if row is None:

            current_count = 0

        else:

            current_count = int(
                row[0]
            )

        # ----------------------------------------------------
        # بررسی سهمیه
        # ----------------------------------------------------

        if current_count >= daily_limit:

            conn.rollback()

            return {

                "allowed":
                    False,

                "used":
                    current_count,

                "remaining":
                    0,

                "date":
                    usage_date,
            }

        # ----------------------------------------------------
        # افزایش شمارنده
        # ----------------------------------------------------

        new_count = (
            current_count + 1
        )

        updated_at = datetime.now(
            timezone.utc
        ).isoformat()

        cursor.execute("""
            INSERT INTO servix_usage (

                usage_date,
                request_count,
                updated_at

            )

            VALUES (?, ?, ?)

            ON CONFLICT(usage_date)

            DO UPDATE SET

                request_count =
                    excluded.request_count,

                updated_at =
                    excluded.updated_at
        """, (

            usage_date,
            new_count,
            updated_at,
        ))

        conn.commit()

        remaining = max(
            0,
            daily_limit - new_count
        )

        return {

            "allowed":
                True,

            "used":
                new_count,

            "remaining":
                remaining,

            "date":
                usage_date,
        }

    except Exception:

        conn.rollback()

        raise

    finally:

        conn.close()


# ============================================================
# GET SERVIX USAGE
# ============================================================

def get_servix_usage(
    daily_limit=SERVIX_DAILY_LIMIT
):
    """
    دریافت وضعیت سهمیه Servix برای امروز.
    """

    usage_date = get_current_utc_date()

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            SELECT

                request_count,
                updated_at

            FROM servix_usage

            WHERE usage_date = ?
        """, (
            usage_date,
        ))

        row = cursor.fetchone()

    finally:

        conn.close()


    if row is None:

        used = 0

        updated_at = None

    else:

        used = int(
            row[0]
        )

        updated_at = row[1]


    remaining = max(
        0,
        daily_limit - used
    )


    return {

        "date":
            usage_date,

        "used":
            used,

        "remaining":
            remaining,

        "limit":
            daily_limit,

        "updated_at":
            updated_at,
    }


# ============================================================
# RESET SERVIX USAGE
# ============================================================

def reset_servix_usage():

    usage_date = get_current_utc_date()

    conn = get_connection()

    try:

        cursor = conn.cursor()

        cursor.execute("""
            DELETE FROM servix_usage

            WHERE usage_date = ?
        """, (
            usage_date,
        ))

        conn.commit()

    finally:

        conn.close()


# ============================================================
# SAVE RAW PRICE
# ============================================================

def save_price(data):

    timestamp = data.get(
        "timestamp"
    )

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
        f"{data['currency']}",
        flush=True
    )


# ============================================================
# GET LATEST RAW PRICES
# ============================================================

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
        f"{len(rows)}",
        flush=True
    )

    return rows


# ============================================================
# GET LATEST PRICE
# ============================================================

def get_latest_price(
    symbol="gold_18k"
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            symbol,
            price,
            currency,
            source,
            timestamp

        FROM gold_prices

        WHERE symbol = ?

        ORDER BY id DESC

        LIMIT 1
    """, (
        symbol,
    ))

    row = cursor.fetchone()

    conn.close()

    return row


# ============================================================
# SAVE CANDLE
# ============================================================

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
        f"{timestamp}",
        flush=True
    )


# ============================================================
# GET CANDLES
# ============================================================

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


# ============================================================
# GET LATEST CANDLE
# ============================================================

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


# ============================================================
# DATABASE STATS
# ============================================================

def get_database_stats():

    conn = get_connection()

    cursor = conn.cursor()

    # --------------------------------------------------------
    # RAW PRICE COUNT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM gold_prices
    """)

    total_prices = cursor.fetchone()[0]

    # --------------------------------------------------------
    # CANDLE COUNT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM gold_candles
    """)

    total_candles = cursor.fetchone()[0]

    # --------------------------------------------------------
    # SOURCE COUNTS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT

            source,
            COUNT(*)

        FROM gold_prices

        GROUP BY source

        ORDER BY source
    """)

    source_rows = cursor.fetchall()

    source_counts = {}

    for source, count in source_rows:

        source_counts[source] = count

    # --------------------------------------------------------
    # TIMEFRAME COUNTS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT

            timeframe,
            COUNT(*)

        FROM gold_candles

        GROUP BY timeframe

        ORDER BY timeframe
    """)

    timeframe_rows = cursor.fetchall()

    timeframe_counts = {}

    for timeframe, count in timeframe_rows:

        timeframe_counts[timeframe] = count

    # --------------------------------------------------------
    # LATEST PRICE
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM gold_prices

        ORDER BY id DESC

        LIMIT 1
    """)

    latest_price_row = cursor.fetchone()

    latest_price_timestamp = (
        latest_price_row[0]
        if latest_price_row
        else None
    )

    # --------------------------------------------------------
    # LATEST CANDLE
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM gold_candles

        ORDER BY id DESC

        LIMIT 1
    """)

    latest_candle_row = cursor.fetchone()

    latest_candle_timestamp = (
        latest_candle_row[0]
        if latest_candle_row
        else None
    )

    # --------------------------------------------------------
    # SERVIX USAGE
    # --------------------------------------------------------

    servix_usage = get_servix_usage()

    conn.close()

    return {

        "total_prices":
            total_prices,

        "total_candles":
            total_candles,

        "source_counts":
            source_counts,

        "timeframe_counts":
            timeframe_counts,

        "latest_price_timestamp":
            latest_price_timestamp,

        "latest_candle_timestamp":
            latest_candle_timestamp,

        "servix_usage":
            servix_usage,
    }


# ============================================================
# DATABASE HEALTH
# ============================================================

def check_database():

    try:

        conn = get_connection()

        cursor = conn.cursor()

        cursor.execute(
            "SELECT 1"
        )

        result = cursor.fetchone()

        conn.close()

        return result == (1,)

    except Exception as error:

        print(
            "❌ DATABASE CHECK ERROR: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )

        return False


# ============================================================
# DIRECT TEST
# ============================================================

if __name__ == "__main__":

    print(
        "========================================"
    )

    print(
        "DATABASE TEST"
    )

    print(
        "========================================"
    )

    # ساخت جداول در صورت نبودن
    init_db()

    # وضعیت Servix
    usage = get_servix_usage()

    print(
        f"📅 Servix date     : "
        f"{usage['date']}"
    )

    print(
        f"📡 Servix used     : "
        f"{usage['used']}"
    )

    print(
        f"📡 Servix remaining: "
        f"{usage['remaining']}"
    )

    print(
        f"📡 Servix limit    : "
        f"{usage['limit']}"
    )

    # وضعیت کلی دیتابیس
    stats = get_database_stats()

    print(
        f"💾 Total prices    : "
        f"{stats['total_prices']}"
    )

    print(
        f"🕯️ Total candles   : "
        f"{stats['total_candles']}"
    )

    print(
        "========================================"
    )
