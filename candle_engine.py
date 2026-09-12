from datetime import datetime, timezone, timedelta

from database import (
    save_candle,
    get_candles,
    get_tgju_price_points_range,
    get_latest_tgju_price_point,
    get_tgju_price_point_count,
)


# ============================================================
# CONFIG
# ============================================================

TIMEFRAME_MINUTES = {
    "1m": 1,
    "5m": 5,
    "15m": 15,
    "1h": 60,
}

RAW_POINTS_LIMIT = 10000

SYMBOL = "gold_18k"


# ============================================================
# TIMESTAMP HELPERS
# ============================================================

def parse_timestamp(timestamp):
    if isinstance(timestamp, datetime):
        dt = timestamp
    else:
        dt = datetime.fromisoformat(str(timestamp))

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)

    return dt.astimezone(timezone.utc)


def timestamp_ms_to_datetime(timestamp_ms):
    return datetime.fromtimestamp(
        int(timestamp_ms) / 1000,
        tz=timezone.utc,
    )


def get_timeframe_start(timestamp, timeframe):
    dt = parse_timestamp(timestamp)

    minutes = TIMEFRAME_MINUTES.get(timeframe)

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
        microsecond=0,
    )


# ============================================================
# SAFE FLOAT
# ============================================================

def safe_float(value):
    try:
        if value is None:
            return None

        number = float(value)

        if number != number:
            return None

        return number

    except (TypeError, ValueError):
        return None


# ============================================================
# RAW TGJU POINTS
# ============================================================

def get_recent_raw_points(
    symbol=SYMBOL,
    limit=RAW_POINTS_LIMIT,
):
    """
    دریافت نقاط خام قیمت TGJU.

    ساختار database.py:

        (
            timestamp_ms,
            timestamp,
            price
        )

    خروجی به ترتیب زمانی قدیمی -> جدید است.
    """

    try:
        rows = get_tgju_price_points(
            symbol=symbol,
            limit=limit,
        )
    except Exception as error:
        print(
            "❌ CANDLE ENGINE: "
            f"Failed to read TGJU raw points: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return []

    if not rows:
        print(
            "⚠️ CANDLE ENGINE: "
            "No TGJU raw points available.",
            flush=True,
        )
        return []

    points = []
    skipped = 0

    for row_index, row in enumerate(rows):

        try:
            if not row or len(row) < 3:
                skipped += 1
                continue

            timestamp_ms = int(row[0])
            timestamp = row[1]
            price = safe_float(row[2])

            if timestamp_ms <= 0:
                skipped += 1
                continue

            if price is None or price <= 0:
                skipped += 1
                continue

            dt = parse_timestamp(
                timestamp
            )

            points.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "timestamp": dt,
                    "price": price,
                }
            )

        except Exception as error:

            skipped += 1

            print(
                "⚠️ CANDLE ENGINE: "
                f"Skipped raw point #{row_index}: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

    points.sort(
        key=lambda item: item["timestamp"]
    )

    print(
        f"📡 CANDLE ENGINE: "
        f"RAW TGJU points read={len(rows)} "
        f"valid={len(points)} "
        f"skipped={skipped}",
        flush=True,
    )

    return points


# ============================================================
# GET COMPLETE RAW POINT WINDOW
# ============================================================

def get_raw_points_for_window(
    start_datetime,
    end_datetime,
    symbol=SYMBOL,
):
    """
    دریافت نقاط خام برای یک بازه مشخص.

    start_datetime inclusive
    end_datetime exclusive
    """

    start_datetime = parse_timestamp(
        start_datetime
    )

    end_datetime = parse_timestamp(
        end_datetime
    )

    start_ms = int(
        start_datetime.timestamp() * 1000
    )

    end_ms = int(
        end_datetime.timestamp() * 1000
    )

    try:
        rows = get_tgju_price_points_range(
            start_timestamp_ms=start_ms,
            end_timestamp_ms=end_ms,
            symbol=symbol,
        )
    except Exception as error:
        print(
            "❌ CANDLE ENGINE: "
            f"Failed to read raw point range: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return []

    points = []

    for row in rows:

        try:
            if len(row) < 3:
                continue

            timestamp_ms = int(row[0])
            timestamp = parse_timestamp(row[1])
            price = safe_float(row[2])

            if price is None or price <= 0:
                continue

            points.append(
                {
                    "timestamp_ms": timestamp_ms,
                    "timestamp": timestamp,
                    "price": price,
                }
            )

        except Exception:
            continue

    points.sort(
        key=lambda item: item["timestamp"]
    )

    return points


# ============================================================
# CURRENT COMPLETE TIME
# ============================================================

def get_current_timeframe_start(
    timeframe,
):
    now = datetime.now(
        timezone.utc
    )

    return get_timeframe_start(
        now,
        timeframe,
    )


# ============================================================
# CHECK COMPLETE BUCKET
# ============================================================

def is_bucket_complete(
    bucket_start,
    timeframe,
):
    """
    فقط بازه‌هایی که کاملاً تمام شده‌اند
    اجازه تبدیل به کندل دارند.
    """

    bucket_start = parse_timestamp(
        bucket_start
    )

    minutes = TIMEFRAME_MINUTES[
        timeframe
    ]

    bucket_end = (
        bucket_start
        + timedelta(
            minutes=minutes
        )
    )

    now = datetime.now(
        timezone.utc
    )

    return bucket_end <= now


# ============================================================
# BUILD OHLC FROM RAW POINTS
# ============================================================

def build_ohlc_from_points(
    points,
    timeframe,
    symbol=SYMBOL,
):
    """
    ساخت یک کندل OHLC واقعی از نقاط خام TGJU.
    """

    if not points:
        return None

    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    valid_points = []

    for point in points:

        try:
            timestamp = parse_timestamp(
                point["timestamp"]
            )

            price = safe_float(
                point["price"]
            )

            if price is None or price <= 0:
                continue

            valid_points.append(
                (
                    timestamp,
                    price,
                )
            )

        except Exception:
            continue

    if not valid_points:
        return None

    valid_points.sort(
        key=lambda item: item[0]
    )

    bucket_start = get_timeframe_start(
        valid_points[0][0],
        timeframe,
    )

    bucket_end = (
        bucket_start
        + timedelta(
            minutes=TIMEFRAME_MINUTES[
                timeframe
            ]
        )
    )

    bucket_points = [
        item
        for item in valid_points
        if (
            item[0] >= bucket_start
            and item[0] < bucket_end
        )
    ]

    if not bucket_points:
        return None

    if not is_bucket_complete(
        bucket_start,
        timeframe,
    ):
        return None

    prices = [
        item[1]
        for item in bucket_points
    ]

    return {
        "symbol": symbol,

        "timeframe":
            timeframe,

        "timestamp":
            bucket_start.isoformat(),

        "open":
            prices[0],

        "high":
            max(prices),

        "low":
            min(prices),

        "close":
            prices[-1],

        "volume":
            0,

        "source_snapshots":
            len(prices),

        "raw_points":
            len(prices),
    }


# ============================================================
# SAVE CANDLE
# ============================================================

def save_candle_data(candle):

    if not candle:
        return False

    try:

        save_candle(
            symbol=candle["symbol"],
            timeframe=candle["timeframe"],
            timestamp=candle["timestamp"],

            open_price=candle["open"],
            high_price=candle["high"],
            low_price=candle["low"],
            close_price=candle["close"],

            volume=candle["volume"],
        )

        return True

    except Exception as error:

        print(
            "❌ CANDLE ENGINE: "
            f"Failed to save candle: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return False


# ============================================================
# PRINT CANDLE
# ============================================================

def print_candle(
    candle,
    title="🕯️ CANDLE",
):

    if not candle:
        return

    print(
        f"{title}:",
        flush=True,
    )

    print(
        f"   Time: {candle['timestamp']}",
        flush=True,
    )

    print(
        f"   TF: {candle['timeframe']}",
        flush=True,
    )

    print(
        f"   Open: "
        f"{candle['open']:,.0f} تومان",
        flush=True,
    )

    print(
        f"   High: "
        f"{candle['high']:,.0f} تومان",
        flush=True,
    )

    print(
        f"   Low: "
        f"{candle['low']:,.0f} تومان",
        flush=True,
    )

    print(
        f"   Close: "
        f"{candle['close']:,.0f} تومان",
        flush=True,
    )

    print(
        f"   Raw points: "
        f"{candle.get('raw_points', candle.get('source_snapshots', 0))}",
        flush=True,
    )


# ============================================================
# BUILD 5M CANDLES FROM RAW TGJU
# ============================================================

def build_5m_candles_from_raw(
    symbol=SYMBOL,
    limit=RAW_POINTS_LIMIT,
):
    """
    RAW TGJU
        ↓
      5M OHLC

    فقط کندل‌های 5 دقیقه‌ای کامل ساخته می‌شوند.
    """

    points = get_recent_raw_points(
        symbol=symbol,
        limit=limit,
    )

    if not points:
        return []

    buckets = {}

    for point in points:

        timestamp = point["timestamp"]

        bucket_start = get_timeframe_start(
            timestamp,
            "5m",
        )

        if not is_bucket_complete(
            bucket_start,
            "5m",
        ):
            continue

        key = bucket_start.isoformat()

        if key not in buckets:
            buckets[key] = []

        buckets[key].append(
            point
        )

    candles = []

    for bucket_key in sorted(
        buckets.keys()
    ):

        bucket_points = buckets[
            bucket_key
        ]

        bucket_points.sort(
            key=lambda item:
            item["timestamp"]
        )

        candle = build_ohlc_from_points(
            points=bucket_points,
            timeframe="5m",
            symbol=symbol,
        )

        if not candle:
            continue

        candles.append(
            candle
        )

        save_candle_data(
            candle
        )

    print(
        f"📊 CANDLE ENGINE: "
        f"5m raw candles built: "
        f"{len(candles)}",
        flush=True,
    )

    return candles


# ============================================================
# BUILD 15M FROM COMPLETE 5M
# ============================================================

def build_15m_from_5m(
    five_minute_candles,
    symbol=SYMBOL,
):
    """
    15M فقط زمانی ساخته می‌شود که
    دقیقاً 3 کندل کامل 5M موجود باشد.
    """

    if not five_minute_candles:
        return []

    buckets = {}

    for candle in five_minute_candles:

        try:
            timestamp = parse_timestamp(
                candle["timestamp"]
            )

            bucket_start = get_timeframe_start(
                timestamp,
                "15m",
            )

            key = bucket_start.isoformat()

            if key not in buckets:
                buckets[key] = []

            buckets[key].append(
                candle
            )

        except Exception:
            continue

    candles = []

    for bucket_key in sorted(
        buckets.keys()
    ):

        values = buckets[
            bucket_key
        ]

        values.sort(
            key=lambda item:
            parse_timestamp(
                item["timestamp"]
            )
        )

        # دقیقاً سه کندل کامل 5m
        if len(values) != 3:
            continue

        bucket_start = parse_timestamp(
            bucket_key
        )

        expected_times = [
            bucket_start
            + timedelta(
                minutes=5 * index
            )
            for index in range(3)
        ]

        actual_times = [
            parse_timestamp(
                candle["timestamp"]
            )
            for candle in values
        ]

        if actual_times != expected_times:
            continue

        if not is_bucket_complete(
            bucket_start,
            "15m",
        ):
            continue

        candle = {
            "symbol": symbol,

            "timeframe":
                "15m",

            "timestamp":
                bucket_start.isoformat(),

            "open":
                values[0]["open"],

            "high":
                max(
                    candle["high"]
                    for candle in values
                ),

            "low":
                min(
                    candle["low"]
                    for candle in values
                ),

            "close":
                values[-1]["close"],

            "volume":
                0,

            "source_snapshots":
                sum(
                    candle.get(
                        "source_snapshots",
                        0,
                    )
                    for candle in values
                ),

            "source_5m_candles":
                3,
        }

        candles.append(
            candle
        )

        save_candle_data(
            candle
        )

    print(
        f"📊 CANDLE ENGINE: "
        f"15m candles built from 5m: "
        f"{len(candles)}",
        flush=True,
    )

    return candles


# ============================================================
# BUILD 1H FROM COMPLETE 5M
# ============================================================

def build_1h_from_5m(
    five_minute_candles,
    symbol=SYMBOL,
):
    """
    1H فقط زمانی ساخته می‌شود که
    دقیقاً 12 کندل کامل 5M موجود باشد.
    """

    if not five_minute_candles:
        return []

    buckets = {}

    for candle in five_minute_candles:

        try:
            timestamp = parse_timestamp(
                candle["timestamp"]
            )

            bucket_start = get_timeframe_start(
                timestamp,
                "1h",
            )

            key = bucket_start.isoformat()

            if key not in buckets:
                buckets[key] = []

            buckets[key].append(
                candle
            )

        except Exception:
            continue

    candles = []

    for bucket_key in sorted(
        buckets.keys()
    ):

        values = buckets[
            bucket_key
        ]

        values.sort(
            key=lambda item:
            parse_timestamp(
                item["timestamp"]
            )
        )

        # دقیقاً 12 کندل کامل 5m
        if len(values) != 12:
            continue

        bucket_start = parse_timestamp(
            bucket_key
        )

        expected_times = [
            bucket_start
            + timedelta(
                minutes=5 * index
            )
            for index in range(12)
        ]

        actual_times = [
            parse_timestamp(
                candle["timestamp"]
            )
            for candle in values
        ]

        if actual_times != expected_times:
            continue

        if not is_bucket_complete(
            bucket_start,
            "1h",
        ):
            continue

        candle = {
            "symbol": symbol,

            "timeframe":
                "1h",

            "timestamp":
                bucket_start.isoformat(),

            "open":
                values[0]["open"],

            "high":
                max(
                    candle["high"]
                    for candle in values
                ),

            "low":
                min(
                    candle["low"]
                    for candle in values
                ),

            "close":
                values[-1]["close"],

            "volume":
                0,

            "source_snapshots":
                sum(
                    candle.get(
                        "source_snapshots",
                        0,
                    )
                    for candle in values
                ),

            "source_5m_candles":
                12,
        }

        candles.append(
            candle
        )

        save_candle_data(
            candle
        )

    print(
        f"📊 CANDLE ENGINE: "
        f"1h candles built from 5m: "
        f"{len(candles)}",
        flush=True,
    )

    return candles


# ============================================================
# BUILD CURRENT 5M CANDLE
# ============================================================

def build_5m_candle(
    symbol=SYMBOL,
):
    """
    برای compatibility.

    آخرین کندل کامل 5M را برمی‌گرداند.
    """

    candles = build_5m_candles_from_raw(
        symbol=symbol,
        limit=RAW_POINTS_LIMIT,
    )

    if not candles:
        return None

    candle = candles[-1]

    print_candle(
        candle,
        "🕯️ CANDLE: Latest 5M",
    )

    return candle


# ============================================================
# BUILD 1M COMPATIBILITY CANDLE
# ============================================================

def build_1m_candle(
    symbol=SYMBOL,
):
    """
    1M واقعی در دیتابیس تولید نمی‌شود.

    این تابع فقط برای compatibility نگه داشته شده.
    """

    try:
        latest = get_latest_tgju_price_point(
            symbol=symbol
        )
    except Exception as error:
        print(
            "❌ CANDLE ENGINE: "
            f"Failed to read latest raw point: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return None

    if not latest:
        return None

    try:
        timestamp_ms = int(
            latest[0]
        )

        timestamp = parse_timestamp(
            latest[1]
        )

        price = safe_float(
            latest[2]
        )

    except Exception:
        return None

    if price is None or price <= 0:
        return None

    return {
        "symbol": symbol,
        "timeframe": "1m",

        "timestamp":
            timestamp.isoformat(),

        "open": price,
        "high": price,
        "low": price,
        "close": price,

        "volume": 0,

        "synthetic": True,

        "raw_timestamp_ms":
            timestamp_ms,
    }


# ============================================================
# GET STORED 1M CANDLES
# ============================================================

def get_recent_1m_candles(
    symbol=SYMBOL,
    limit=500,
):

    rows = get_candles(
        symbol=symbol,
        timeframe="1m",
        limit=limit,
    )

    candles = []

    for row in rows:

        try:

            if len(row) < 6:
                continue

            candles.append(
                {
                    "symbol": symbol,
                    "timeframe": "1m",

                    "timestamp": row[0],

                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],

                    "volume": row[5],
                }
            )

        except Exception:
            continue

    candles.sort(
        key=lambda candle:
        parse_timestamp(
            candle["timestamp"]
        )
    )

    return candles


# ============================================================
# GET STORED CANDLES
# ============================================================

def get_recent_candles(
    timeframe,
    symbol=SYMBOL,
    limit=500,
):

    rows = get_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=limit,
    )

    candles = []

    for row in rows:

        try:

            if len(row) < 6:
                continue

            candles.append(
                {
                    "symbol": symbol,
                    "timeframe": timeframe,

                    "timestamp": row[0],

                    "open": row[1],
                    "high": row[2],
                    "low": row[3],
                    "close": row[4],

                    "volume": row[5],
                }
            )

        except Exception:
            continue

    candles.sort(
        key=lambda candle:
        parse_timestamp(
            candle["timestamp"]
        )
    )

    return candles


# ============================================================
# BUILD TIMEFRAME CANDLES
# ============================================================

def build_timeframe_candles(
    timeframe,
    symbol=SYMBOL,
    limit=RAW_POINTS_LIMIT,
):

    if timeframe not in TIMEFRAME_MINUTES:

        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    # --------------------------------------------------------
    # 1M
    # --------------------------------------------------------

    if timeframe == "1m":

        return get_recent_1m_candles(
            symbol=symbol,
            limit=limit,
        )

    # --------------------------------------------------------
    # BUILD BASE 5M
    # --------------------------------------------------------

    five_minute_candles = (
        build_5m_candles_from_raw(
            symbol=symbol,
            limit=limit,
        )
    )

    if timeframe == "5m":

        return five_minute_candles

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    if timeframe == "15m":

        return build_15m_from_5m(
            five_minute_candles=
                five_minute_candles,
            symbol=symbol,
        )

    # --------------------------------------------------------
    # 1H
    # --------------------------------------------------------

    if timeframe == "1h":

        return build_1h_from_5m(
            five_minute_candles=
                five_minute_candles,
            symbol=symbol,
        )

    return []


# ============================================================
# BUILD ALL TIMEFRAMES
# ============================================================

def build_all_timeframes(
    symbol=SYMBOL,
):

    results = {}

    # --------------------------------------------------------
    # 1M
    # --------------------------------------------------------

    results["1m"] = (
        get_recent_1m_candles(
            symbol=symbol,
            limit=500,
        )
    )

    # --------------------------------------------------------
    # BUILD 5M ONCE
    # --------------------------------------------------------

    five_minute_candles = (
        build_5m_candles_from_raw(
            symbol=symbol,
            limit=RAW_POINTS_LIMIT,
        )
    )

    results["5m"] = (
        five_minute_candles
    )

    # --------------------------------------------------------
    # 15M
    # --------------------------------------------------------

    results["15m"] = (
        build_15m_from_5m(
            five_minute_candles=
                five_minute_candles,
            symbol=symbol,
        )
    )

    # --------------------------------------------------------
    # 1H
    # --------------------------------------------------------

    results["1h"] = (
        build_1h_from_5m(
            five_minute_candles=
                five_minute_candles,
            symbol=symbol,
        )
    )

    return results


# ============================================================
# GET LATEST CANDLE
# ============================================================

def get_latest_timeframe_candle(
    timeframe,
    symbol=SYMBOL,
):

    rows = get_candles(
        symbol=symbol,
        timeframe=timeframe,
        limit=1,
    )

    if not rows:
        return None

    row = rows[0]

    if len(row) < 6:
        return None

    return {
        "symbol": symbol,

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
# DATABASE / CANDLE DIAGNOSTIC
# ============================================================

def diagnose_candle_engine():

    print(
        "\n"
        "========================================\n"
        "🧪 CANDLE ENGINE DIAGNOSTIC\n"
        "========================================",
        flush=True,
    )

    # --------------------------------------------------------
    # RAW POINT COUNT
    # --------------------------------------------------------

    try:
        raw_count = get_tgju_price_point_count(
            symbol=SYMBOL
        )

        print(
            f"📡 TGJU RAW POINTS: "
            f"{raw_count}",
            flush=True,
        )

    except Exception as error:

        print(
            "❌ RAW POINT COUNT FAILED: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

    # --------------------------------------------------------
    # LATEST RAW POINT
    # --------------------------------------------------------

    try:

        latest = get_latest_tgju_price_point(
            symbol=SYMBOL
        )

        if latest:

            print(
                f"🕐 Latest raw point: "
                f"{latest[1]}",
                flush=True,
            )

            print(
                f"💰 Latest raw price: "
                f"{float(latest[2]):,.0f} تومان",
                flush=True,
            )

    except Exception as error:

        print(
            "❌ LATEST RAW POINT FAILED: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

    # --------------------------------------------------------
    # BUILD TIMEFRAMES
    # --------------------------------------------------------

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        try:

            candles = (
                build_timeframe_candles(
                    timeframe=timeframe,
                    symbol=SYMBOL,
                    limit=RAW_POINTS_LIMIT,
                )
            )

            print(
                f"🕯️ {timeframe}: "
                f"{len(candles)} candles",
                flush=True,
            )

            if candles:

                print_candle(
                    candles[-1],
                    f"📊 LATEST {timeframe}",
                )

        except Exception as error:

            print(
                f"❌ {timeframe} diagnostic error: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )

    print(
        "========================================\n",
        flush=True,
    )


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    print(
        "🧪 CANDLE ENGINE TEST",
        flush=True,
    )

    try:

        diagnose_candle_engine()

        print(
            "⚠️ 1M note: "
            "Real 1M candle generation is disabled. "
            "Raw TGJU points are used for 5M base candles.",
            flush=True,
        )

        print(
            "\n✅ CANDLE ENGINE TEST FINISHED",
            flush=True,
        )

    except Exception as error:

        print(
            "❌ CANDLE ENGINE TEST FAILED: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
