from datetime import datetime, timezone, timedelta

from database import (
    get_connection,
    save_candle,
)


# ==========================================
# Settings
# ==========================================

TIMEFRAME = "1m"


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

    dt = dt.replace(
        second=0,
        microsecond=0
    )

    return dt


# ==========================================
# Get Raw Prices
# ==========================================

def get_recent_prices(
    symbol="gold_18k",
    minutes=5
):

    conn = get_connection()

    cursor = conn.cursor()

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
        minutes * 20
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ==========================================
# Build Candle From Prices
# ==========================================

def build_candle_from_prices(
    prices,
    minute_start
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

    volume = len(values)

    return {
        "symbol": "gold_18k",
        "timeframe": TIMEFRAME,
        "timestamp": minute_start.isoformat(),
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }


# ==========================================
# Build 1 Minute Candle
# ==========================================

def build_1m_candle(
    symbol="gold_18k"
):

    prices = get_recent_prices(
        symbol=symbol,
        minutes=5
    )

    if not prices:

        print(
            "⚠️ CANDLE: No raw price data."
        )

        return None

    # آخرین timestamp
    latest_timestamp = prices[0][1]

    latest_minute = get_minute_start(
        latest_timestamp
    )

    candle = build_candle_from_prices(
        prices,
        latest_minute
    )

    if not candle:

        print(
            "⚠️ CANDLE: Could not build "
            "current 1M candle."
        )

        return None

    # ذخیره / بروزرسانی کندل جاری
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

    # ======================================
    # Check Previous Closed Candle
    # ======================================

    previous_minute = (
        latest_minute
        - timedelta(minutes=1)
    )

    previous_candle = build_candle_from_prices(
        prices,
        previous_minute
    )

    if previous_candle:

        save_candle(
            symbol=previous_candle["symbol"],
            timeframe=previous_candle["timeframe"],
            timestamp=previous_candle["timestamp"],
            open_price=previous_candle["open"],
            high_price=previous_candle["high"],
            low_price=previous_candle["low"],
            close_price=previous_candle["close"],
            volume=previous_candle["volume"]
        )

        print(
            "🔒 CANDLE: Previous 1M candle "
            "closed and saved."
        )

        print(
            f"   Time: "
            f"{previous_candle['timestamp']}"
        )

        print(
            f"   Open: "
            f"{previous_candle['open']:,}"
        )

        print(
            f"   High: "
            f"{previous_candle['high']:,}"
        )

        print(
            f"   Low: "
            f"{previous_candle['low']:,}"
        )

        print(
            f"   Close: "
            f"{previous_candle['close']:,}"
        )

        print(
            f"   Samples: "
            f"{previous_candle['volume']}"
        )

    # ======================================
    # Current Candle Information
    # ======================================

    print(
        "🕯️ CANDLE: Current 1M candle updated."
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

    return candle
