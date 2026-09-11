from datetime import datetime, timezone, timedelta

from database import (
    get_connection,
    save_candle,
)


# ==========================================
# Settings
# ==========================================

TIMEFRAME = "1m"

# تعداد رکوردهای خام برای بررسی
RAW_PRICE_LIMIT = 200


# ==========================================
# Parse Timestamp
# ==========================================

def parse_timestamp(timestamp):

    dt = datetime.fromisoformat(
        timestamp
    )

    if dt.tzinfo is None:

        dt = dt.replace(
            tzinfo=timezone.utc
        )

    return dt.astimezone(
        timezone.utc
    )


# ==========================================
# Get Minute Start
# ==========================================

def get_minute_start(timestamp):

    dt = parse_timestamp(
        timestamp
    )

    return dt.replace(
        second=0,
        microsecond=0
    )


# ==========================================
# Get Raw Prices
# ==========================================

def get_recent_prices(
    symbol="gold_18k",
    limit=RAW_PRICE_LIMIT
):

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("""
            SELECT
                price,
                timestamp
            FROM gold_prices

            WHERE symbol = ?

            ORDER BY id DESC

            LIMIT ?
        """, (
            symbol,
            limit
        ))

        rows = cursor.fetchall()

    finally:

        conn.close()

    return rows


# ==========================================
# Build Candle From Prices
# ==========================================

def build_candle_from_prices(
    prices,
    minute_start,
    symbol="gold_18k"
):

    minute_end = (
        minute_start
        + timedelta(minutes=1)
    )

    minute_prices = []

    for price, timestamp in prices:

        try:

            dt = parse_timestamp(
                timestamp
            )

        except Exception:

            continue

        if (
            dt >= minute_start
            and dt < minute_end
        ):

            minute_prices.append(
                (price, dt)
            )

    if not minute_prices:

        return None

    # مرتب‌سازی بر اساس زمان
    minute_prices.sort(
        key=lambda item: item[1]
    )

    values = [
        item[0]
        for item in minute_prices
    ]

    open_price = values[0]

    high_price = max(values)

    low_price = min(values)

    close_price = values[-1]

    # تعداد نمونه‌های دریافتی
    volume = len(values)

    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "timestamp": minute_start.isoformat(),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


# ==========================================
# Save Candle Helper
# ==========================================

def save_candle_data(candle):

    save_candle(
        symbol=candle["symbol"],
        timeframe=candle["timeframe"],
        timestamp=candle["timestamp"],
        open_price=candle["open"],
        high_price=candle["high"],
        low_price=candle["low"],
        close_price=candle["close"],
        volume=candle["volume"]
    )


# ==========================================
# Print Candle
# ==========================================

def print_candle(
    candle,
    title
):

    print(
        title
    )

    print(
        f"   Time: "
        f"{candle['timestamp']}"
    )

    print(
        f"   Open: "
        f"{candle['open']:,}"
    )

    print(
        f"   High: "
        f"{candle['high']:,}"
    )

    print(
        f"   Low: "
        f"{candle['low']:,}"
    )

    print(
        f"   Close: "
        f"{candle['close']:,}"
    )

    print(
        f"   Samples: "
        f"{candle['volume']}"
    )


# ==========================================
# Build 1 Minute Candle
# ==========================================

def build_1m_candle(
    symbol="gold_18k"
):

    prices = get_recent_prices(
        symbol=symbol,
        limit=RAW_PRICE_LIMIT
    )

    if not prices:

        print(
            "⚠️ CANDLE: No raw price data."
        )

        return None

    # --------------------------------------
    # پیدا کردن آخرین timestamp معتبر
    # --------------------------------------

    latest_timestamp = None

    for price, timestamp in prices:

        try:

            parse_timestamp(
                timestamp
            )

            latest_timestamp = timestamp

            break

        except Exception:

            continue

    if not latest_timestamp:

        print(
            "⚠️ CANDLE: No valid timestamps."
        )

        return None

    # --------------------------------------
    # دقیقه جاری
    # --------------------------------------

    latest_minute = get_minute_start(
        latest_timestamp
    )

    current_candle = build_candle_from_prices(
        prices=prices,
        minute_start=latest_minute,
        symbol=symbol
    )

    if not current_candle:

        print(
            "⚠️ CANDLE: Could not build "
            "current 1M candle."
        )

        return None

    # --------------------------------------
    # ذخیره / بروزرسانی کندل جاری
    # --------------------------------------

    save_candle_data(
        current_candle
    )

    # --------------------------------------
    # کندل دقیقه قبل
    # --------------------------------------

    previous_minute = (
        latest_minute
        - timedelta(minutes=1)
    )

    previous_candle = build_candle_from_prices(
        prices=prices,
        minute_start=previous_minute,
        symbol=symbol
    )

    if previous_candle:

        save_candle_data(
            previous_candle
        )

        print_candle(
            previous_candle,
            "🔒 CANDLE: Previous 1M candle saved."
        )

    else:

        print(
            "ℹ️ CANDLE: Previous 1M candle "
            "not available yet."
        )

    # --------------------------------------
    # نمایش کندل جاری
    # --------------------------------------

    print_candle(
        current_candle,
        "🕯️ CANDLE: Current 1M candle updated."
    )

    return current_candle
