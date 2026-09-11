from datetime import datetime, timezone

from database import (
    get_connection,
    save_candle,
)


# ==========================================
# Candle Timeframe
# ==========================================

TIMEFRAME = "1m"


# ==========================================
# Get Minute Start
# ==========================================

def get_minute_start(timestamp):

    dt = datetime.fromisoformat(
        timestamp
    )

    dt = dt.astimezone(timezone.utc)

    dt = dt.replace(
        second=0,
        microsecond=0
    )

    return dt.isoformat()


# ==========================================
# Build 1 Minute Candle
# ==========================================

def build_1m_candle(symbol="gold_18k"):

    conn = get_connection()

    cursor = conn.cursor()

    # آخرین قیمت ثبت‌شده
    cursor.execute("""
        SELECT
            price,
            timestamp
        FROM gold_prices

        WHERE symbol = ?

        ORDER BY id DESC

        LIMIT 1
    """, (
        symbol,
    ))

    latest = cursor.fetchone()

    if not latest:

        conn.close()

        print(
            "⚠️ No price data available."
        )

        return None

    latest_price, latest_timestamp = latest

    # شروع دقیقه‌ای که قیمت در آن قرار دارد
    minute_start = get_minute_start(
        latest_timestamp
    )

    # تمام قیمت‌های همان دقیقه
    cursor.execute("""
        SELECT
            price,
            timestamp
        FROM gold_prices

        WHERE symbol = ?
        AND timestamp >= ?
        AND timestamp < datetime(?, '+1 minute')

        ORDER BY timestamp ASC
    """, (
        symbol,
        minute_start,
        minute_start
    ))

    rows = cursor.fetchall()

    conn.close()

    if not rows:

        print(
            "⚠️ No prices found for candle."
        )

        return None

    prices = [
        row[0]
        for row in rows
    ]

    # ======================================
    # OHLC
    # ======================================

    open_price = prices[0]

    high_price = max(prices)

    low_price = min(prices)

    close_price = prices[-1]

    volume = len(prices)

    # ======================================
    # Save Candle
    # ======================================

    save_candle(
        symbol=symbol,
        timeframe=TIMEFRAME,
        timestamp=minute_start,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume
    )

    print(
        "🕯️ 1M Candle created:"
    )

    print(
        f"   Time: {minute_start}"
    )

    print(
        f"   Open: {open_price:,}"
    )

    print(
        f"   High: {high_price:,}"
    )

    print(
        f"   Low: {low_price:,}"
    )

    print(
        f"   Close: {close_price:,}"
    )

    print(
        f"   Samples: {volume}"
    )

    return {
        "symbol": symbol,
        "timeframe": TIMEFRAME,
        "timestamp": minute_start,
        "open": open_price,
        "high": high_price,
        "low": low_price,
        "close": close_price,
        "volume": volume,
    }
