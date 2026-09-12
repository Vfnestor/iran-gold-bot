import os
import json
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
# ما عمداً فقط 45 درخواست را استفاده می‌کنیم.
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

    # ========================================================
    # LEGACY RAW GOLD PRICES
    # ========================================================
    #
    # این جدول برای سازگاری با نسخه قبلی پروژه نگه داشته شده.
    #
    # در معماری جدید Collector نباید قیمت‌های لحظه‌ای را
    # در این جدول ذخیره کند.
    #
    # جدول فعلاً حذف نمی‌شود تا اطلاعات قبلی از بین نرود.
    #

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

    # ========================================================
    # GOLD CANDLES
    # ========================================================

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

    # ========================================================
    # MARKET SNAPSHOTS
    # ========================================================
    #
    # هر رکورد = یک وضعیت بازار در یک زمان مشخص.
    #
    # قرار است Collector در معماری جدید تقریباً هر 5 دقیقه
    # یک Snapshot ایجاد کند.
    #
    # قیمت‌های لحظه‌ای 10 ثانیه‌ای در این جدول ذخیره نمی‌شوند.
    #
    # منابع:
    #
    # TGJU       -> gold_18k_toman
    # World Gold -> xau_usd
    # USD/Toman  -> usd_buy / usd_sell / usd_mid
    # Servix     -> servix_gold_18k_toman
    #
    # Servix می‌تواند NULL باشد.
    #

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS market_snapshots (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT NOT NULL,

            gold_18k_toman REAL,

            world_gold_usd REAL,

            usd_buy_toman REAL,

            usd_sell_toman REAL,

            usd_mid_toman REAL,

            servix_gold_18k_toman REAL,

            servix_timestamp TEXT,

            tgju_timestamp TEXT,

            world_gold_timestamp TEXT,

            usd_timestamp TEXT,

            created_at TEXT NOT NULL,

            UNIQUE(timestamp)
        )
    """)

    # ========================================================
    # ANALYSIS HISTORY
    # ========================================================
    #
    # فقط نتیجه تحلیل در این جدول ذخیره می‌شود.
    #
    # قیمت‌های خام لحظه‌ای اینجا ذخیره نمی‌شوند.
    #
    # این جدول بعداً تاریخچه اصلی دکمه «📊 تاریخچه» خواهد بود.
    #

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS analysis_history (

            id INTEGER PRIMARY KEY AUTOINCREMENT,

            timestamp TEXT NOT NULL,

            symbol TEXT NOT NULL,

            price_toman REAL,

            signal TEXT,

            trend TEXT,

            confidence REAL,

            entry REAL,

            stop_loss REAL,

            take_profit_1 REAL,

            take_profit_2 REAL,

            take_profit_3 REAL,

            risk_reward REAL,

            rsi REAL,

            macd REAL,

            macd_signal REAL,

            ema_fast REAL,

            ema_slow REAL,

            atr REAL,

            momentum REAL,

            support REAL,

            resistance REAL,

            world_gold_usd REAL,

            usd_mid_toman REAL,

            fair_value_toman REAL,

            source_spread REAL,

            analysis_data TEXT,

            created_at TEXT NOT NULL
        )
    """)

    # ========================================================
    # SERVIX DAILY QUOTA
    # ========================================================

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS servix_usage (

            usage_date TEXT PRIMARY KEY,

            request_count INTEGER NOT NULL DEFAULT 0,

            updated_at TEXT NOT NULL
        )
    """)

    # ========================================================
    # INDEXES - LEGACY RAW PRICES
    # ========================================================

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

    # ========================================================
    # INDEXES - CANDLES
    # ========================================================

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

    # ========================================================
    # INDEXES - MARKET SNAPSHOTS
    # ========================================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_market_snapshots_timestamp

        ON market_snapshots(timestamp)
    """)

    # ========================================================
    # INDEXES - ANALYSIS HISTORY
    # ========================================================

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_analysis_history_timestamp

        ON analysis_history(timestamp)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_analysis_history_signal

        ON analysis_history(signal)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS
        idx_analysis_history_symbol

        ON analysis_history(symbol)
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
# CURRENT UTC TIMESTAMP
# ============================================================

def get_current_timestamp():

    return datetime.now(
        timezone.utc
    ).isoformat()


# ============================================================
# RESERVE SERVIX REQUEST
# ============================================================

def reserve_servix_request(
    daily_limit=SERVIX_DAILY_LIMIT
):
    """
    رزرو یک درخواست Servix.

    قبل از ارسال HTTP request فراخوانی می‌شود.

    اگر سهمیه موجود باشد:
        allowed = True

    اگر سهمیه تمام شده باشد:
        allowed = False
    """

    usage_date = get_current_utc_date()

    conn = get_connection()

    try:

        cursor = conn.cursor()

        conn.execute(
            "BEGIN IMMEDIATE"
        )

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

        if current_count >= daily_limit:

            conn.rollback()

            return {

                "allowed": False,

                "used": current_count,

                "remaining": 0,

                "date": usage_date,
            }

        new_count = (
            current_count + 1
        )

        updated_at = get_current_timestamp()

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

            "allowed": True,

            "used": new_count,

            "remaining": remaining,

            "date": usage_date,
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

        "date": usage_date,

        "used": used,

        "remaining": remaining,

        "limit": daily_limit,

        "updated_at": updated_at,
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
# SAVE LEGACY RAW PRICE
# ============================================================
#
# این تابع برای سازگاری با فایل‌های قدیمی نگه داشته شده.
#
# در مرحله Collector بعدی دیگر از این تابع برای ذخیره
# قیمت‌های لحظه‌ای استفاده نخواهیم کرد.
#

def save_price(data):

    timestamp = data.get(
        "timestamp"
    )

    if not timestamp:

        timestamp = get_current_timestamp()

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
        f"💾 Legacy price saved: "
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
# SAVE MARKET SNAPSHOT
# ============================================================

def save_market_snapshot(
    timestamp=None,
    gold_18k_toman=None,
    world_gold_usd=None,
    usd_buy_toman=None,
    usd_sell_toman=None,
    usd_mid_toman=None,
    servix_gold_18k_toman=None,
    servix_timestamp=None,
    tgju_timestamp=None,
    world_gold_timestamp=None,
    usd_timestamp=None
):
    """
    ذخیره یک Snapshot از وضعیت بازار.

    هر Snapshot نماینده یک لحظه مشخص از بازار است.

    قیمت‌های لحظه‌ای در اینجا ذخیره نمی‌شوند؛
    Collector باید تقریباً هر 5 دقیقه یک Snapshot بسازد.
    """

    if timestamp is None:

        timestamp = get_current_timestamp()

    created_at = get_current_timestamp()

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO market_snapshots (

            timestamp,

            gold_18k_toman,

            world_gold_usd,

            usd_buy_toman,
            usd_sell_toman,
            usd_mid_toman,

            servix_gold_18k_toman,

            servix_timestamp,

            tgju_timestamp,
            world_gold_timestamp,
            usd_timestamp,

            created_at

        )

        VALUES (

            ?,

            ?,

            ?,

            ?,
            ?,
            ?,

            ?,

            ?,

            ?,
            ?,
            ?,

            ?

        )

        ON CONFLICT(timestamp)

        DO UPDATE SET

            gold_18k_toman =
                excluded.gold_18k_toman,

            world_gold_usd =
                excluded.world_gold_usd,

            usd_buy_toman =
                excluded.usd_buy_toman,

            usd_sell_toman =
                excluded.usd_sell_toman,

            usd_mid_toman =
                excluded.usd_mid_toman,

            servix_gold_18k_toman =
                excluded.servix_gold_18k_toman,

            servix_timestamp =
                excluded.servix_timestamp,

            tgju_timestamp =
                excluded.tgju_timestamp,

            world_gold_timestamp =
                excluded.world_gold_timestamp,

            usd_timestamp =
                excluded.usd_timestamp
    """, (

        timestamp,

        gold_18k_toman,

        world_gold_usd,

        usd_buy_toman,
        usd_sell_toman,
        usd_mid_toman,

        servix_gold_18k_toman,

        servix_timestamp,

        tgju_timestamp,
        world_gold_timestamp,
        usd_timestamp,

        created_at
    ))

    conn.commit()

    conn.close()

    print(
        f"📊 Market snapshot saved: "
        f"{timestamp}",
        flush=True
    )


# ============================================================
# GET MARKET HISTORY
# ============================================================

def get_market_history(
    limit=100
):
    """
    دریافت تاریخچه Snapshotهای بازار.

    جدیدترین رکورد ابتدا برمی‌گردد.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            timestamp,

            gold_18k_toman,

            world_gold_usd,

            usd_buy_toman,
            usd_sell_toman,
            usd_mid_toman,

            servix_gold_18k_toman,

            servix_timestamp,

            tgju_timestamp,
            world_gold_timestamp,
            usd_timestamp

        FROM market_snapshots

        ORDER BY timestamp DESC

        LIMIT ?
    """, (
        limit,
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# GET LATEST MARKET SNAPSHOT
# ============================================================

def get_latest_market_snapshot():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            timestamp,

            gold_18k_toman,

            world_gold_usd,

            usd_buy_toman,
            usd_sell_toman,
            usd_mid_toman,

            servix_gold_18k_toman,

            servix_timestamp,

            tgju_timestamp,
            world_gold_timestamp,
            usd_timestamp

        FROM market_snapshots

        ORDER BY timestamp DESC

        LIMIT 1
    """)

    row = cursor.fetchone()

    conn.close()

    return row


# ============================================================
# SAVE ANALYSIS
# ============================================================

def save_analysis(
    analysis
):
    """
    ذخیره نتیجه نهایی موتور تحلیل.

    analysis می‌تواند علاوه بر فیلدهای اصلی،
    اطلاعات اضافی را نیز داخل analysis_data داشته باشد.
    """

    timestamp = (
        analysis.get("timestamp")
        or get_current_timestamp()
    )

    created_at = get_current_timestamp()

    # --------------------------------------------------------
    # اطلاعات تکمیلی تحلیل
    # --------------------------------------------------------

    analysis_data = analysis.get(
        "analysis_data"
    )

    if analysis_data is None:

        analysis_data = {}

    if not isinstance(
        analysis_data,
        str
    ):

        try:

            analysis_data = json.dumps(
                analysis_data,
                ensure_ascii=False
            )

        except (
            TypeError,
            ValueError
        ):

            analysis_data = "{}"

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO analysis_history (

            timestamp,

            symbol,

            price_toman,

            signal,

            trend,

            confidence,

            entry,

            stop_loss,

            take_profit_1,
            take_profit_2,
            take_profit_3,

            risk_reward,

            rsi,

            macd,
            macd_signal,

            ema_fast,
            ema_slow,

            atr,

            momentum,

            support,
            resistance,

            world_gold_usd,

            usd_mid_toman,

            fair_value_toman,

            source_spread,

            analysis_data,

            created_at

        )

        VALUES (

            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?,
            ?

        )
    """, (

        timestamp,

        analysis.get(
            "symbol",
            "gold_18k"
        ),

        analysis.get(
            "price_toman"
        ),

        analysis.get(
            "signal"
        ),

        analysis.get(
            "trend"
        ),

        analysis.get(
            "confidence"
        ),

        analysis.get(
            "entry"
        ),

        analysis.get(
            "stop_loss"
        ),

        analysis.get(
            "take_profit_1"
        ),

        analysis.get(
            "take_profit_2"
        ),

        analysis.get(
            "take_profit_3"
        ),

        analysis.get(
            "risk_reward"
        ),

        analysis.get(
            "rsi"
        ),

        analysis.get(
            "macd"
        ),

        analysis.get(
            "macd_signal"
        ),

        analysis.get(
            "ema_fast"
        ),

        analysis.get(
            "ema_slow"
        ),

        analysis.get(
            "atr"
        ),

        analysis.get(
            "momentum"
        ),

        analysis.get(
            "support"
        ),

        analysis.get(
            "resistance"
        ),

        analysis.get(
            "world_gold_usd"
        ),

        analysis.get(
            "usd_mid_toman"
        ),

        analysis.get(
            "fair_value_toman"
        ),

        analysis.get(
            "source_spread"
        ),

        analysis_data,

        created_at
    ))

    conn.commit()

    analysis_id = cursor.lastrowid

    conn.close()

    print(
        f"🧠 Analysis saved: "
        f"id={analysis_id} "
        f"signal={analysis.get('signal')}",
        flush=True
    )

    return analysis_id


# ============================================================
# GET ANALYSIS HISTORY
# ============================================================

def get_analysis_history(
    limit=20
):
    """
    تاریخچه اصلی تحلیل.

    این تابع همان چیزی است که بعداً دکمه
    «📊 تاریخچه» از آن استفاده خواهد کرد.

    قیمت‌های خام منابع اینجا نمایش داده نمی‌شوند.
    """

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            id,

            timestamp,

            symbol,

            price_toman,

            signal,

            trend,

            confidence,

            entry,

            stop_loss,

            take_profit_1,
            take_profit_2,
            take_profit_3,

            risk_reward,

            rsi,

            macd,
            macd_signal,

            ema_fast,
            ema_slow,

            atr,

            momentum,

            support,
            resistance,

            world_gold_usd,

            usd_mid_toman,

            fair_value_toman,

            source_spread,

            analysis_data

        FROM analysis_history

        ORDER BY timestamp DESC

        LIMIT ?
    """, (
        limit,
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ============================================================
# GET LATEST ANALYSIS
# ============================================================

def get_latest_analysis():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT

            id,

            timestamp,

            symbol,

            price_toman,

            signal,

            trend,

            confidence,

            entry,

            stop_loss,

            take_profit_1,
            take_profit_2,
            take_profit_3,

            risk_reward,

            rsi,

            macd,
            macd_signal,

            ema_fast,
            ema_slow,

            atr,

            momentum,

            support,
            resistance,

            world_gold_usd,

            usd_mid_toman,

            fair_value_toman,

            source_spread,

            analysis_data

        FROM analysis_history

        ORDER BY timestamp DESC

        LIMIT 1
    """)

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

    created_at = get_current_timestamp()

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
    # LEGACY RAW PRICE COUNT
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
    # MARKET SNAPSHOT COUNT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM market_snapshots
    """)

    total_market_snapshots = (
        cursor.fetchone()[0]
    )

    # --------------------------------------------------------
    # ANALYSIS COUNT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT COUNT(*)
        FROM analysis_history
    """)

    total_analyses = (
        cursor.fetchone()[0]
    )

    # --------------------------------------------------------
    # SOURCE COUNTS - LEGACY
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
    # LATEST MARKET SNAPSHOT
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM market_snapshots

        ORDER BY timestamp DESC

        LIMIT 1
    """)

    latest_snapshot_row = (
        cursor.fetchone()
    )

    latest_snapshot_timestamp = (
        latest_snapshot_row[0]
        if latest_snapshot_row
        else None
    )

    # --------------------------------------------------------
    # LATEST ANALYSIS
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM analysis_history

        ORDER BY timestamp DESC

        LIMIT 1
    """)

    latest_analysis_row = (
        cursor.fetchone()
    )

    latest_analysis_timestamp = (
        latest_analysis_row[0]
        if latest_analysis_row
        else None
    )

    # --------------------------------------------------------
    # LATEST CANDLE
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM gold_candles

        ORDER BY timestamp DESC

        LIMIT 1
    """)

    latest_candle_row = (
        cursor.fetchone()
    )

    latest_candle_timestamp = (
        latest_candle_row[0]
        if latest_candle_row
        else None
    )

    # --------------------------------------------------------
    # LEGACY LATEST PRICE
    # --------------------------------------------------------

    cursor.execute("""
        SELECT timestamp

        FROM gold_prices

        ORDER BY id DESC

        LIMIT 1
    """)

    latest_price_row = (
        cursor.fetchone()
    )

    latest_price_timestamp = (
        latest_price_row[0]
        if latest_price_row
        else None
    )

    conn.close()

    # --------------------------------------------------------
    # SERVIX USAGE
    # --------------------------------------------------------

    servix_usage = get_servix_usage()

    return {

        "total_prices":
            total_prices,

        "total_candles":
            total_candles,

        "total_market_snapshots":
            total_market_snapshots,

        "total_analyses":
            total_analyses,

        "source_counts":
            source_counts,

        "timeframe_counts":
            timeframe_counts,

        "latest_price_timestamp":
            latest_price_timestamp,

        "latest_snapshot_timestamp":
            latest_snapshot_timestamp,

        "latest_analysis_timestamp":
            latest_analysis_timestamp,

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

    # ساخت جداول
    init_db()

    # --------------------------------------------------------
    # SERVIX STATUS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # DATABASE STATUS
    # --------------------------------------------------------

    stats = get_database_stats()

    print(
        f"💾 Legacy prices   : "
        f"{stats['total_prices']}"
    )

    print(
        f"📊 Market snapshots: "
        f"{stats['total_market_snapshots']}"
    )

    print(
        f"🧠 Analyses        : "
        f"{stats['total_analyses']}"
    )

    print(
        f"🕯️ Total candles   : "
        f"{stats['total_candles']}"
    )

    print(
        "========================================"
    )
