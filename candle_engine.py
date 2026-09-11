from datetime import (
    datetime,
    timezone,
    timedelta,
)

from database import (
    get_connection,
    save_candle,
    get_candles,
)


# ============================================================
# CONFIG
# ============================================================

RAW_PRICE_LIMIT = 500

ONE_MINUTE = 60

TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}


# ============================================================
# TIMESTAMP HELPERS
# ============================================================

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


def get_minute_start(timestamp):

    dt = parse_timestamp(
        timestamp
    )

    return dt.replace(
        second=0,
        microsecond=0
    )


def get_timeframe_start(
    timestamp,
    timeframe
):

    dt = parse_timestamp(
        timestamp
    )

    minutes = TIMEFRAME_MINUTES.get(
        timeframe
    )

    if not minutes:

        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    total_minutes = (
        dt.hour * 60
        + dt.minute
    )

    bucket_minutes = (
        total_minutes // minutes
    ) * minutes

    hour = bucket_minutes // 60
    minute = bucket_minutes % 60

    return dt.replace(
        hour=hour,
        minute=minute,
        second=0,
        microsecond=0
    )


# ============================================================
# RAW PRICE DATA
# ============================================================

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


# ============================================================
# BUILD 1 MINUTE CANDLE
# ============================================================

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

        "timeframe": "1m",

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


# ============================================================
# SAVE CANDLE
# ============================================================

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


# ============================================================
# PRINT CANDLE
# ============================================================

def print_candle(
    candle,
    title="🕯️ CANDLE"
):

    if not candle:

        return

    print(
        f"{title}:",
        flush=True
    )

    print(
        f"   Time: "
        f"{candle['timestamp']}",
        flush=True
    )

    print(
        f"   Open: "
        f"{candle['open']:,}",
        flush=True
    )

    print(
        f"   High: "
        f"{candle['high']:,}",
        flush=True
    )

    print(
        f"   Low: "
        f"{candle['low']:,}",
        flush=True
    )

    print(
        f"   Close: "
        f"{candle['close']:,}",
        flush=True
    )

    print(
        f"   Samples: "
        f"{candle['volume']}",
        flush=True
    )


# ============================================================
# BUILD CURRENT 1M CANDLE
# ============================================================

def build_1m_candle(
    symbol="gold_18k"
):

    prices = get_recent_prices(
        symbol=symbol
    )

    if not prices:

        print(
            "⚠️ CANDLE: "
            "No raw price data.",
            flush=True
        )

        return None

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
            "No valid timestamps.",
            flush=True
        )

        return None

    latest_minute = get_minute_start(
        latest_timestamp
    )

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

    previous_minute = (
        latest_minute
        - timedelta(minutes=1)
    )

    previous_candle = build_candle_from_prices(

        prices,

        previous_minute,

        symbol=symbol
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
        "Current 1M candle updated.",
        flush=True
    )

    return current_candle


# ============================================================
# GET 1M CANDLES
# ============================================================

def get_recent_1m_candles(
    symbol="gold_18k",
    limit=500
):

    rows = get_candles(

        symbol=symbol,

        timeframe="1m",

        limit=limit
    )

    candles = []

    for row in rows:

        timestamp = row[0]

        open_price = row[1]

        high_price = row[2]

        low_price = row[3]

        close_price = row[4]

        volume = row[5]

        candles.append({

            "symbol": symbol,

            "timeframe": "1m",

            "timestamp": timestamp,

            "open": open_price,

            "high": high_price,

            "low": low_price,

            "close": close_price,

            "volume": volume,
        })

    candles.sort(
        key=lambda candle:
        parse_timestamp(
            candle["timestamp"]
        )
    )

    return candles


# ============================================================
# AGGREGATE 1M CANDLES
# ============================================================

def aggregate_candles(
    candles,
    timeframe
):

    if not candles:

        return []

    if timeframe not in TIMEFRAME_MINUTES:

        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    if timeframe == "1m":

        return candles

    result = []

    buckets = {}

    for candle in candles:

        timestamp = candle["timestamp"]

        try:

            bucket_start = get_timeframe_start(

                timestamp,

                timeframe
            )

        except Exception:

            continue

        bucket_key = (
            bucket_start.isoformat()
        )

        if bucket_key not in buckets:

            buckets[bucket_key] = []

        buckets[bucket_key].append(
            candle
        )

    sorted_bucket_keys = sorted(
        buckets.keys()
    )

    for bucket_key in sorted_bucket_keys:

        bucket_candles = buckets[
            bucket_key
        ]

        bucket_candles.sort(
            key=lambda candle:
            parse_timestamp(
                candle["timestamp"]
            )
        )

        if not bucket_candles:

            continue

        first = bucket_candles[0]

        last = bucket_candles[-1]

        open_price = first["open"]

        close_price = last["close"]

        high_price = max(
            candle["high"]
            for candle in bucket_candles
        )

        low_price = min(
            candle["low"]
            for candle in bucket_candles
        )

        volume = sum(
            candle["volume"]
            for candle in bucket_candles
        )

        result.append({

            "symbol":
                first["symbol"],

            "timeframe":
                timeframe,

            "timestamp":
                bucket_key,

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

            "source_candles":
                len(bucket_candles),
        })

    return result


# ============================================================
# BUILD HIGHER TIMEFRAME CANDLES
# ============================================================

def build_timeframe_candles(
    timeframe,
    symbol="gold_18k",
    limit=500
):

    if timeframe not in TIMEFRAME_MINUTES:

        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    if timeframe == "1m":

        return get_recent_1m_candles(

            symbol=symbol,

            limit=limit
        )

    one_minute_candles = get_recent_1m_candles(

        symbol=symbol,

        limit=limit
    )

    if not one_minute_candles:

        print(
            f"⚠️ CANDLE: "
            f"No 1M candles available "
            f"for {timeframe}.",
            flush=True
        )

        return []

    higher_candles = aggregate_candles(

        one_minute_candles,

        timeframe
    )

    for candle in higher_candles:

        save_candle_data(
            candle
        )

    print(
        f"📊 CANDLE ENGINE: "
        f"{timeframe} candles built: "
        f"{len(higher_candles)}",
        flush=True
    )

    return higher_candles


# ============================================================
# BUILD ALL CURRENT TIMEFRAMES
# ============================================================

def build_all_timeframes(
    symbol="gold_18k"
):

    timeframes = [
        "1m",
        "5m",
        "15m",
        "1h",
    ]

    results = {}

    for timeframe in timeframes:

        try:

            candles = build_timeframe_candles(

                timeframe=timeframe,

                symbol=symbol,

                limit=500
            )

            results[timeframe] = candles

        except Exception as error:

            print(
                f"❌ CANDLE ENGINE: "
                f"{timeframe} error: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True
            )

            results[timeframe] = []

    return results


# ============================================================
# GET LATEST CANDLE FROM DATABASE
# ============================================================

def get_latest_timeframe_candle(
    timeframe,
    symbol="gold_18k"
):

    rows = get_candles(

        symbol=symbol,

        timeframe=timeframe,

        limit=1
    )

    if not rows:

        return None

    row = rows[0]

    return {

        "symbol":
            symbol,

        "timeframe":
            timeframe,

        "timestamp":
            row[0],

        "open":
            row[1],

        "high":
            row[2],

        "low":
            row[3],

        "close":
            row[4],

        "volume":
            row[5],
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "🧪 CANDLE ENGINE TEST",
        flush=True
    )

    try:

        build_1m_candle()

        print(
            "",
            flush=True
        )

        build_timeframe_candles(
            "5m"
        )

        build_timeframe_candles(
            "15m"
        )

        build_timeframe_candles(
            "1h"
        )

        print(
            "",
            flush=True
        )

        for timeframe in [
            "1m",
            "5m",
            "15m",
            "1h"
        ]:

            candle = get_latest_timeframe_candle(
                timeframe
            )

            if candle:

                print_candle(
                    candle,
                    f"📊 LATEST {timeframe}"
                )

            else:

                print(
                    f"⚠️ "
                    f"No {timeframe} candle.",
                    flush=True
                )

        print(
            "",
            flush=True
        )

        print(
            "✅ CANDLE ENGINE TEST FINISHED",
            flush=True
        )

    except Exception as error:

        print(
            "❌ CANDLE ENGINE TEST FAILED: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )
