from datetime import datetime, timezone, timedelta

from database import (
    save_candle,
    get_candles,
    get_market_history,
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

SNAPSHOT_LIMIT = 500


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
# MARKET SNAPSHOT HELPERS
# ============================================================

def get_recent_snapshots(limit=SNAPSHOT_LIMIT):
    """
    دریافت Snapshotهای بازار از database.py.

    ساختار واقعی get_market_history():

        0  timestamp
        1  gold_18k_toman
        2  world_gold_usd
        3  usd_buy_toman
        4  usd_sell_toman
        5  usd_mid_toman
        6  servix_gold_18k_toman
        7  servix_timestamp
        8  tgju_timestamp
        9  world_gold_timestamp
        10 usd_timestamp
    """

    try:
        rows = get_market_history(
            limit=limit
        )

    except Exception as error:
        print(
            "❌ CANDLE ENGINE: "
            f"Failed to read market snapshots: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )
        return []

    if not rows:
        print(
            "⚠️ CANDLE ENGINE: "
            "Database returned 0 market snapshots.",
            flush=True,
        )
        return []

    snapshots = []
    skipped = 0

    for row_index, row in enumerate(rows):

        try:
            if not row or len(row) < 11:
                skipped += 1

                print(
                    f"⚠️ CANDLE ENGINE: "
                    f"Invalid snapshot row #{row_index}: "
                    f"expected 11 columns, "
                    f"got {len(row) if row else 0}",
                    flush=True,
                )

                continue

            timestamp = row[0]

            gold_price = safe_float(
                row[1]
            )

            if not timestamp:
                skipped += 1
                continue

            if gold_price is None:
                skipped += 1
                continue

            if gold_price <= 0:
                skipped += 1
                continue

            snapshot = {
                "timestamp": timestamp,

                "gold_18k_toman":
                    gold_price,

                "world_gold_usd":
                    safe_float(row[2]),

                "usd_buy_toman":
                    safe_float(row[3]),

                "usd_sell_toman":
                    safe_float(row[4]),

                "usd_mid_toman":
                    safe_float(row[5]),

                "servix_gold_18k_toman":
                    safe_float(row[6]),

                "servix_timestamp":
                    row[7],

                "tgju_timestamp":
                    row[8],

                "world_gold_timestamp":
                    row[9],

                "usd_timestamp":
                    row[10],
            }

            parse_timestamp(
                snapshot["timestamp"]
            )

            snapshots.append(
                snapshot
            )

        except Exception as error:

            skipped += 1

            print(
                "⚠️ CANDLE ENGINE: "
                f"Skipped snapshot #{row_index}: "
                f"{type(error).__name__}: {error}",
                flush=True,
            )

    snapshots.sort(
        key=lambda item:
        parse_timestamp(
            item["timestamp"]
        )
    )

    print(
        f"📡 CANDLE ENGINE: "
        f"Snapshots read={len(rows)} "
        f"valid={len(snapshots)} "
        f"skipped={skipped}",
        flush=True,
    )

    return snapshots


# ============================================================
# BUILD CANDLE FROM SNAPSHOTS
# ============================================================

def build_candle_from_snapshots(
    snapshots,
    timeframe,
    symbol="gold_18k",
):

    if not snapshots:
        return None

    if timeframe not in TIMEFRAME_MINUTES:
        raise ValueError(
            f"Unsupported timeframe: {timeframe}"
        )

    valid = []

    for snapshot in snapshots:

        try:
            timestamp = parse_timestamp(
                snapshot["timestamp"]
            )

            price = safe_float(
                snapshot["gold_18k_toman"]
            )

            if price is None or price <= 0:
                continue

            valid.append(
                (
                    timestamp,
                    price,
                )
            )

        except Exception:
            continue

    if not valid:
        return None

    valid.sort(
        key=lambda item: item[0]
    )

    bucket_start = get_timeframe_start(
        valid[-1][0],
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

    bucket_values = [
        item
        for item in valid
        if (
            item[0] >= bucket_start
            and item[0] < bucket_end
        )
    ]

    if not bucket_values:
        return None

    prices = [
        item[1]
        for item in bucket_values
    ]

    return {
        "symbol": symbol,
        "timeframe": timeframe,

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
            len(prices),

        "source_snapshots":
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
        f"   Samples: "
        f"{candle.get('source_snapshots', candle['volume'])}",
        flush=True,
    )


# ============================================================
# BUILD CURRENT 5M CANDLE
# ============================================================

def build_5m_candle(
    symbol="gold_18k",
):

    snapshots = get_recent_snapshots(
        limit=SNAPSHOT_LIMIT
    )

    if not snapshots:

        print(
            "⚠️ CANDLE ENGINE: "
            "No market snapshots available.",
            flush=True,
        )

        return None

    candle = build_candle_from_snapshots(
        snapshots=snapshots,
        timeframe="5m",
        symbol=symbol,
    )

    if candle:

        save_candle_data(
            candle
        )

        print_candle(
            candle,
            "🕯️ CANDLE: Current 5M",
        )

    return candle


# ============================================================
# BUILD 1M COMPATIBILITY CANDLE
# ============================================================

def build_1m_candle(
    symbol="gold_18k",
):

    """
    1M واقعی نداریم چون Snapshot هر 5 دقیقه ذخیره می‌شود.

    این تابع فقط برای compatibility نگه داشته شده.
    """

    snapshots = get_recent_snapshots(
        limit=1
    )

    if not snapshots:

        print(
            "⚠️ CANDLE ENGINE: "
            "No market snapshot for "
            "1M compatibility.",
            flush=True,
        )

        return None

    snapshot = snapshots[-1]

    timestamp = parse_timestamp(
        snapshot["timestamp"]
    )

    price = safe_float(
        snapshot["gold_18k_toman"]
    )

    if price is None:
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

        "volume": 1,
        "synthetic": True,
    }


# ============================================================
# GET STORED 1M CANDLES
# ============================================================

def get_recent_1m_candles(
    symbol="gold_18k",
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
    symbol="gold_18k",
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
    symbol="gold_18k",
    limit=SNAPSHOT_LIMIT,
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
    # MARKET SNAPSHOTS
    # --------------------------------------------------------

    snapshots = get_recent_snapshots(
        limit=limit
    )

    if not snapshots:

        print(
            f"⚠️ CANDLE ENGINE: "
            f"No market snapshots for "
            f"{timeframe}.",
            flush=True,
        )

        return []

    # --------------------------------------------------------
    # GROUP SNAPSHOTS
    # --------------------------------------------------------

    buckets = {}

    for snapshot in snapshots:

        try:

            timestamp = parse_timestamp(
                snapshot["timestamp"]
            )

            price = safe_float(
                snapshot["gold_18k_toman"]
            )

            if price is None or price <= 0:
                continue

            bucket_start = get_timeframe_start(
                timestamp,
                timeframe,
            )

            key = bucket_start.isoformat()

            if key not in buckets:
                buckets[key] = []

            buckets[key].append(
                (
                    timestamp,
                    price,
                )
            )

        except Exception as error:

            print(
                "⚠️ CANDLE ENGINE: "
                f"Invalid snapshot while "
                f"building {timeframe}: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )

            continue

    # --------------------------------------------------------
    # BUILD CANDLES
    # --------------------------------------------------------

    candles = []

    for bucket_key in sorted(
        buckets.keys()
    ):

        values = buckets[
            bucket_key
        ]

        values.sort(
            key=lambda item: item[0]
        )

        if not values:
            continue

        prices = [
            item[1]
            for item in values
        ]

        candle = {
            "symbol": symbol,

            "timeframe":
                timeframe,

            "timestamp":
                bucket_key,

            "open":
                prices[0],

            "high":
                max(prices),

            "low":
                min(prices),

            "close":
                prices[-1],

            "volume":
                len(prices),

            "source_snapshots":
                len(values),
        }

        candles.append(
            candle
        )

        save_candle_data(
            candle
        )

    print(
        f"📊 CANDLE ENGINE: "
        f"{timeframe} candles built: "
        f"{len(candles)}",
        flush=True,
    )

    return candles


# ============================================================
# BUILD ALL TIMEFRAMES
# ============================================================

def build_all_timeframes(
    symbol="gold_18k",
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
    # 5M / 15M / 1H
    # --------------------------------------------------------

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        try:

            results[timeframe] = (
                build_timeframe_candles(
                    timeframe=timeframe,
                    symbol=symbol,
                    limit=500,
                )
            )

        except Exception as error:

            print(
                f"❌ CANDLE ENGINE: "
                f"{timeframe} error: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True,
            )

            results[timeframe] = []

    return results


# ============================================================
# GET LATEST CANDLE
# ============================================================

def get_latest_timeframe_candle(
    timeframe,
    symbol="gold_18k",
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

    snapshots = get_recent_snapshots(
        limit=20
    )

    print(
        f"📡 Valid snapshots: "
        f"{len(snapshots)}",
        flush=True,
    )

    if snapshots:

        first = snapshots[0]
        last = snapshots[-1]

        print(
            f"🕐 Oldest snapshot: "
            f"{first['timestamp']}",
            flush=True,
        )

        print(
            f"🕐 Newest snapshot: "
            f"{last['timestamp']}",
            flush=True,
        )

        print(
            f"💰 Latest gold: "
            f"{last['gold_18k_toman']:,.0f} تومان",
            flush=True,
        )

    for timeframe in (
        "5m",
        "15m",
        "1h",
    ):

        candles = (
            build_timeframe_candles(
                timeframe=timeframe,
                symbol="gold_18k",
                limit=500,
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
            "Raw 1M candle generation is disabled "
            "because raw prices are no longer stored.",
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
