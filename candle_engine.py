from datetime import (
    datetime,
    timezone,
    timedelta,
)

from database import (
    get_connection,
    save_candle,
)


TIMEFRAME = "1m"

RAW_PRICE_LIMIT = 200


# ==========================================
# Timestamp Parser
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
# Minute Start
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
# Get Recent Raw Prices
# ==========================================

def get_recent_prices(
    symbol="gold_18k",
    limit=RAW_PRICE_LIMIT
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
        limit
    ))

    rows = cursor.fetchall()

    conn.close()

    return rows


# ==========================================
# Build Candle
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
                (
                    price,
                    dt
                )
            )

    if not minute_prices:

        return None

    minute_prices.sort(
        key=lambda item: item[1]
    )

    values = [
        item[0]
        for item in minute_prices
    ]

    open_price = values[0]

    high_price = max(
        values
    )

    low_price = min(
        values
    )

    close_price = values[-1]

    volume = len(
        values
    )

    return {

        "symbol": symbol,

        "timeframe": TIMEFRAME,

        "timestamp":
            minute_start.isoformat(),

        "open":
            open_price,

        "high":
            high_price,

        "low":
            low_price,

        "close":
            close_price,

        "volume":
            volume,
    }


# ==========================================
# Save Candle Data
# ==========================================

def save_candle_data(
    candle
):

    if not candle:

        return

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
    title="🕯️ CANDLE"
):

    if not candle:

        return

    print(
        f"{title}:"
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
# Build 1M Candle
# ==========================================

def build_1m_candle(
    symbol="gold_18k"
):

    prices = get_recent_prices(
        symbol=symbol
    )

    if not prices:

        print(
            "⚠️ CANDLE: "
            "No raw price data."
        )

        return None

    # ------------------------------
    # Find latest valid timestamp
    # ------------------------------

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
            "⚠️ CANDLE: "
            "No valid timestamps."
        )

        return None

    latest_minute = get_minute_start(
        latest_timestamp
    )

    # ------------------------------
    # Current candle
    # ------------------------------

    current_candle = build_candle_from_prices(

        prices,

        latest_minute,

        symbol=symbol
    )

    if current_candle:

        save_candle_data(
            current_candle
        )

        print_candle(
            current_candle,
            "🕯️ CANDLE: Current 1M"
        )

    # ------------------------------
    # Previous candle
    # ------------------------------

    previous_minute = (
        latest_minute
        - timedelta(minutes=1)
    )

    previous_candle = (
        build_candle_from_prices(

            prices,

            previous_minute,

            symbol=symbol
        )
    )

    if previous_candle:

        save_candle_data(
            previous_candle
        )

        print_candle(
            previous_candle,
            "🔒 CANDLE: Previous 1M"
        )

    print(
        "🕯️ CANDLE: "
        "Current 1M candle updated."
    )

    return current_candle
