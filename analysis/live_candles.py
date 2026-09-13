from datetime import datetime, timezone, timedelta

from database import (
    get_tgju_price_points,
    get_latest_tgju_price_point,
)


# ============================================================
# CONFIG
# ============================================================

SYMBOL = "gold_18k"

# حداقل تعداد کندل برای اینکه تحلیل اصلاً شروع شود
MIN_CANDLES_FOR_ANALYSIS = 1

# تعداد کندل برای اعتماد کامل به تحلیل
RELIABLE_CANDLE_COUNT = 25

# فقط داده‌های این بازه وارد موتور Live Candle می‌شوند
LIVE_WINDOW_MINUTES = 180

# محدوده منطقی قیمت نسبت به قیمت فعلی
MIN_PRICE_RATIO = 0.70
MAX_PRICE_RATIO = 1.30


# ============================================================
# HELPERS
# ============================================================
def get_live_analysis_candles(
    window_minutes=LIVE_WINDOW_MINUTES
):
def get_live_candles(
    window_minutes=LIVE_WINDOW_MINUTES
):
    return get_live_analysis_candles(
        window_minutes=window_minutes
    )

def _safe_float(value):
    try:
        if value is None:
            return None

        if isinstance(value, bool):
            return None

        return float(value)

    except Exception:
        return None


def _safe_timestamp(value):
    """
    تبدیل timestampهای مختلف به datetime timezone-aware.
    """

    if value is None:
        return None

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    try:
        number = float(value)

        # milliseconds
        if number > 10_000_000_000:
            number /= 1000

        return datetime.fromtimestamp(
            number,
            tz=timezone.utc,
        )

    except Exception:
        return None


def _extract_value(item, key, default=None):
    """
    خواندن امن مقدار از dict / tuple / object.

    این تابع برای جلوگیری از خطای:
        'tuple' object has no attribute 'get'
    استفاده می‌شود.
    """

    if item is None:
        return default

    # dict
    if isinstance(item, dict):
        return item.get(key, default)

    # object
    if hasattr(item, key):
        try:
            return getattr(item, key)
        except Exception:
            pass

    # tuple/list
    if isinstance(item, (tuple, list)):

        # ترتیب‌های رایج:
        # (timestamp, price)
        # (price, timestamp)

        if key in ("timestamp", "time", "created_at"):
            if len(item) >= 1:
                return item[0]

        if key in ("price", "value"):
            if len(item) >= 2:
                return item[1]

    return default


def _normalize_point(item):
    """
    تبدیل یک رکورد دیتابیس به ساختار استاندارد:

        {
            timestamp: datetime,
            price: float
        }
    """

    timestamp = _extract_value(
        item,
        "timestamp",
    )

    if timestamp is None:
        timestamp = _extract_value(
            item,
            "time",
        )

    if timestamp is None:
        timestamp = _extract_value(
            item,
            "created_at",
        )

    price = _extract_value(
        item,
        "price",
    )

    if price is None:
        price = _extract_value(
            item,
            "value",
        )

    timestamp = _safe_timestamp(
        timestamp
    )

    price = _safe_float(
        price
    )

    if timestamp is None or price is None:
        return None

    if price <= 0:
        return None

    return {
        "timestamp": timestamp,
        "price": price,
    }


# ============================================================
# MARKET SNAPSHOT
# ============================================================

def _get_snapshot_price():
    """
    دریافت قیمت از market snapshot.

    snapshot ممکن است dict یا tuple باشد.
    بنابراین دیگر مستقیماً .get() روی آن اجرا نمی‌کنیم.
    """

    try:
        snapshot = get_latest_tgju_price_point(
            symbol=SYMBOL
        )

    except TypeError:

        try:
            snapshot = get_latest_tgju_price_point(
                SYMBOL
            )

        except Exception as error:
            print(
                "⚠️ LIVE CANDLES: "
                f"market snapshot unavailable: "
                f"{type(error).__name__}({error!r})",
                flush=True,
            )

            return None

    except Exception as error:

        print(
            "⚠️ LIVE CANDLES: "
            f"market snapshot unavailable: "
            f"{type(error).__name__}({error!r})",
            flush=True,
        )

        return None

    if snapshot is None:
        return None

    # --------------------------------------------------------
    # dict
    # --------------------------------------------------------

    if isinstance(snapshot, dict):

        for key in (
            "price",
            "value",
            "last_price",
            "current_price",
        ):

            price = _safe_float(
                snapshot.get(key)
            )

            if price is not None:
                return price

    # --------------------------------------------------------
    # tuple / list
    # --------------------------------------------------------

    if isinstance(snapshot, (tuple, list)):

        # حالت‌های رایج:
        #
        # (timestamp, price)
        # (price, timestamp)
        #
        for value in snapshot:

            price = _safe_float(
                value
            )

            if price is None:
                continue

            # قیمت منطقی طلای 18K
            if (
                50_000_000
                <= price
                <= 1_000_000_000
            ):
                return price

    # --------------------------------------------------------
    # object
    # --------------------------------------------------------

    for key in (
        "price",
        "value",
        "last_price",
        "current_price",
    ):

        try:

            price = _safe_float(
                getattr(
                    snapshot,
                    key,
                    None,
                )
            )

            if price is not None:
                return price

        except Exception:
            continue

    return None


# ============================================================
# PRICE REFERENCE
# ============================================================

def _get_price_reference(points):
    """
    تعیین قیمت مرجع.

    اول market snapshot
    سپس آخرین نقطه معتبر TGJU
    """

    snapshot_price = _get_snapshot_price()

    if snapshot_price is not None:

        print(
            f"💰 LIVE PRICE REFERENCE: "
            f"{snapshot_price:,.0f} TOMAN",
            flush=True,
        )

        return snapshot_price

    if points:

        price = points[-1]["price"]

        print(
            f"💰 LIVE PRICE REFERENCE: "
            f"{price:,.0f} TOMAN "
            f"(latest TGJU point)",
            flush=True,
        )

        return price

    return None


# ============================================================
# LOAD TGJU POINTS
# ============================================================

def _load_valid_points():

    print(
        "📡 LIVE CANDLES: "
        "reading stored TGJU points...",
        flush=True,
    )

    try:

        rows = get_tgju_price_points(
            symbol=SYMBOL,
            limit=5000,
        )

    except TypeError:

        rows = get_tgju_price_points(
            SYMBOL,
            5000,
        )

    except Exception as error:

        print(
            "🔴 LIVE CANDLES: "
            f"database read failed: "
            f"{type(error).__name__}: {error}",
            flush=True,
        )

        return []

    if rows is None:
        rows = []

    print(
        f"📊 DATABASE TGJU RAW ROWS: "
        f"{len(rows)}",
        flush=True,
    )

    normalized = []

    rejected_timestamp = 0
    rejected_price = 0

    now = datetime.now(
        timezone.utc
    )

    for row in rows:

        point = _normalize_point(
            row
        )

        if point is None:

            # تشخیص تقریبی برای لاگ
            raw_timestamp = _extract_value(
                row,
                "timestamp",
            )

            raw_price = _extract_value(
                row,
                "price",
            )

            if (
                _safe_timestamp(
                    raw_timestamp
                )
                is None
            ):
                rejected_timestamp += 1

            elif (
                _safe_float(
                    raw_price
                )
                is None
            ):
                rejected_price += 1

            else:
                rejected_price += 1

            continue

        timestamp = point[
            "timestamp"
        ]

        price = point[
            "price"
        ]

        # ----------------------------------------------------
        # timestamp validation
        # ----------------------------------------------------

        if timestamp > (
            now + timedelta(minutes=5)
        ):

            rejected_timestamp += 1
            continue

        # ----------------------------------------------------
        # absolute price validation
        # ----------------------------------------------------

        if (
            price < 50_000_000
            or price > 1_000_000_000
        ):

            rejected_price += 1
            continue

        normalized.append(
            point
        )

    # --------------------------------------------------------
    # Sort
    # --------------------------------------------------------

    normalized.sort(
        key=lambda item: item[
            "timestamp"
        ]
    )

    print(
        f"📊 VALID 18K POINTS: "
        f"{len(normalized)}",
        flush=True,
    )

    print(
        f"⚠️ REJECTED TIMESTAMP: "
        f"{rejected_timestamp}",
        flush=True,
    )

    print(
        f"⚠️ REJECTED PRICE: "
        f"{rejected_price}",
        flush=True,
    )

    return normalized


# ============================================================
# FILTER OUTLIERS
# ============================================================

def _filter_outliers(
    points,
    reference_price,
):

    if not points:
        return []

    if reference_price is None:
        return points

    min_price = (
        reference_price
        * MIN_PRICE_RATIO
    )

    max_price = (
        reference_price
        * MAX_PRICE_RATIO
    )

    print(
        f"🛡️ VALID PRICE RANGE: "
        f"{min_price:,.0f} → "
        f"{max_price:,.0f} TOMAN",
        flush=True,
    )

    valid = []
    rejected = 0

    for point in points:

        price = point[
            "price"
        ]

        if (
            price < min_price
            or price > max_price
        ):

            rejected += 1
            continue

        valid.append(
            point
        )

    print(
        f"🛡️ REJECTED OUTLIERS: "
        f"{rejected}",
        flush=True,
    )

    return valid


# ============================================================
# LIVE WINDOW
# ============================================================

def _apply_live_window(points):

    if not points:
        return []

    last_timestamp = points[-1][
        "timestamp"
    ]

    window_start = (
        last_timestamp
        - timedelta(
            minutes=LIVE_WINDOW_MINUTES
        )
    )

    print(
        f"⏱️ LIVE WINDOW: "
        f"{window_start.isoformat()} → "
        f"{last_timestamp.isoformat()}",
        flush=True,
    )

    result = [
        point
        for point in points
        if (
            window_start
            <= point["timestamp"]
            <= last_timestamp
        )
    ]

    print(
        f"📊 VALID POINTS IN WINDOW: "
        f"{len(result)}",
        flush=True,
    )

    return result


# ============================================================
# CANDLE BUILDER
# ============================================================

def _floor_timestamp(
    timestamp,
    minutes,
):

    timestamp = timestamp.replace(
        second=0,
        microsecond=0,
    )

    minute = (
        timestamp.minute
    )

    floored = (
        minute
        - (
            minute % minutes
        )
    )

    return timestamp.replace(
        minute=floored
    )


def _build_candles(
    points,
    interval_minutes,
):

    buckets = {}

    for point in points:

        timestamp = point[
            "timestamp"
        ]

        bucket_time = _floor_timestamp(
            timestamp,
            interval_minutes,
        )

        if bucket_time not in buckets:

            buckets[
                bucket_time
            ] = {
                "timestamp": bucket_time,
                "open": point["price"],
                "high": point["price"],
                "low": point["price"],
                "close": point["price"],
                "volume": 1,
            }

        else:

            candle = buckets[
                bucket_time
            ]

            price = point[
                "price"
            ]

            candle["high"] = max(
                candle["high"],
                price,
            )

            candle["low"] = min(
                candle["low"],
                price,
            )

            candle["close"] = price

            candle["volume"] += 1

    candles = list(
        buckets.values()
    )

    candles.sort(
        key=lambda item: item[
            "timestamp"
        ]
    )

    return candles


# ============================================================
# ANALYSIS STATUS
# ============================================================

def _analysis_status(
    candle_count,
):

    if candle_count < MIN_CANDLES_FOR_ANALYSIS:

        return {
            "can_analyze": False,
            "reliable": False,
            "status": "insufficient_data",
            "status_fa": "داده کافی برای تحلیل وجود ندارد",
            "candle_count": candle_count,
            "required_for_reliable": RELIABLE_CANDLE_COUNT,
        }

    if candle_count < RELIABLE_CANDLE_COUNT:

        return {
            "can_analyze": True,
            "reliable": False,
            "status": "unreliable",
            "status_fa": "⚠️ تحلیل غیر قابل اعتماد",
            "candle_count": candle_count,
            "required_for_reliable": RELIABLE_CANDLE_COUNT,
        }

    return {
        "can_analyze": True,
        "reliable": True,
        "status": "reliable",
        "status_fa": "✅ تحلیل قابل اعتماد",
        "candle_count": candle_count,
        "required_for_reliable": RELIABLE_CANDLE_COUNT,
    }


# ============================================================
# MAIN
# ============================================================

def get_live_analysis_candles():

    points = _load_valid_points()

    if not points:

        print(
            "ℹ️ ANALYSIS: "
            "no valid TGJU points.",
            flush=True,
        )

        return {
            "5m": [],
            "15m": [],
            "1h": [],
            "analysis": _analysis_status(0),
            "can_analyze": False,
            "reliable": False,
            "reliability": "unreliable",
            "reliability_text": (
                "داده کافی برای تحلیل وجود ندارد"
            ),
        }

    # ========================================================
    # PRICE REFERENCE
    # ========================================================

    reference_price = _get_price_reference(
        points
    )

    if reference_price is None:

        reference_price = points[-1][
            "price"
        ]

    # ========================================================
    # OUTLIER FILTER
    # ========================================================

    points = _filter_outliers(
        points,
        reference_price,
    )

    if not points:

        print(
            "🛑 ANALYSIS: "
            "all points rejected.",
            flush=True,
        )

        return {
            "5m": [],
            "15m": [],
            "1h": [],
            "analysis": _analysis_status(0),
            "can_analyze": False,
            "reliable": False,
            "reliability": "unreliable",
            "reliability_text": (
                "داده معتبر برای تحلیل وجود ندارد"
            ),
        }

    # ========================================================
    # DIAGNOSTIC
    # ========================================================

    first = points[0]
    last = points[-1]

    print(
        f"🕐 FIRST VALID POINT: "
        f"{first['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        f"🕐 LAST VALID POINT: "
        f"{last['timestamp'].isoformat()}",
        flush=True,
    )

    print(
        f"💰 LAST VALID PRICE: "
        f"{last['price']:,.0f} TOMAN",
        flush=True,
    )

    # ========================================================
    # LIVE WINDOW
    # ========================================================

    points = _apply_live_window(
        points
    )

    if not points:

        return {
            "5m": [],
            "15m": [],
            "1h": [],
            "analysis": _analysis_status(0),
            "can_analyze": False,
            "reliable": False,
            "reliability": "unreliable",
            "reliability_text": (
                "داده کافی برای تحلیل وجود ندارد"
            ),
        }

    # ========================================================
    # BUILD CANDLES
    # ========================================================

    candles_5m = _build_candles(
        points,
        5,
    )

    candles_15m = _build_candles(
        points,
        15,
    )

    candles_1h = _build_candles(
        points,
        60,
    )

    # ========================================================
    # DIAGNOSTIC
    # ========================================================

    print(
        f"🕯️ LIVE CANDLES: "
        f"5m={len(candles_5m)} "
        f"15m={len(candles_15m)} "
        f"1h={len(candles_1h)}",
        flush=True,
    )

    if candles_5m:

        print(
            f"🕯️ 5M FIRST: "
            f"{candles_5m[0]['timestamp'].isoformat()}",
            flush=True,
        )

        print(
            f"🕯️ 5M LAST: "
            f"{candles_5m[-1]['timestamp'].isoformat()}",
            flush=True,
        )

        print(
            f"💰 5M LAST CLOSE: "
            f"{candles_5m[-1]['close']:,.0f} TOMAN",
            flush=True,
        )

    # ========================================================
    # ANALYSIS STATUS
    # ========================================================

    analysis_status = _analysis_status(
        len(candles_5m)
    )

    if not analysis_status[
        "can_analyze"
    ]:

        print(
            f"ℹ️ ANALYSIS: "
            f"not enough 5m candles "
            f"({len(candles_5m)}/"
            f"{RELIABLE_CANDLE_COUNT})",
            flush=True,
        )

    elif not analysis_status[
        "reliable"
    ]:

        print(
            f"⚠️ ANALYSIS: "
            f"running with only "
            f"{len(candles_5m)} "
            f"5m candles "
            f"(reliable at "
            f"{RELIABLE_CANDLE_COUNT})",
            flush=True,
        )

    else:

        print(
            f"✅ ANALYSIS: "
            f"{len(candles_5m)} "
            f"5m candles — reliable",
            flush=True,
        )

    # ========================================================
    # RESULT
    # ========================================================

    result = {
        "5m": candles_5m,
        "15m": candles_15m,
        "1h": candles_1h,

        # ----------------------------------------------------
        # analysis metadata
        # ----------------------------------------------------

        "analysis": analysis_status,

        "can_analyze": analysis_status[
            "can_analyze"
        ],

        "reliable": analysis_status[
            "reliable"
        ],

        "reliability": (
            "reliable"
            if analysis_status["reliable"]
            else "unreliable"
        ),

        "reliability_text": analysis_status[
            "status_fa"
        ],

        "candle_count": len(
            candles_5m
        ),

        "required_for_reliable": (
            RELIABLE_CANDLE_COUNT
        ),

        # ----------------------------------------------------
        # price
        # ----------------------------------------------------

        "price": reference_price,

        "current_price": reference_price,

        "symbol": SYMBOL,

        "currency": "IRR",

        "source": "tgju",

        "generated_at": datetime.now(
            timezone.utc
        ).isoformat(),
    }

    print(
        f"📡 LIVE 5M CANDLES: "
        f"{len(candles_5m)}",
        flush=True,
    )

    if (
        analysis_status["can_analyze"]
        and not analysis_status["reliable"]
    ):

        print(
            "⚠️ RELIABILITY: "
            "UNRELIABLE — "
            f"{len(candles_5m)}/"
            f"{RELIABLE_CANDLE_COUNT} candles",
            flush=True,
        )

    elif analysis_status[
        "reliable"
    ]:

        print(
            "✅ RELIABILITY: "
            "RELIABLE",
            flush=True,
        )

    return result


# ============================================================
# ALIAS
# ============================================================

def get_live_candles():
    """
    سازگاری با بخش‌های قدیمی پروژه.
    """

    return get_live_analysis_candles()
