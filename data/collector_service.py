import time
import traceback

from dotenv import load_dotenv

from data.collectors.tgju import get_gold_18k

from database import save_price

from candle_engine import (
    build_1m_candle,
    build_timeframe_candles,
)


# ============================================================
# ENV
# ============================================================

load_dotenv()


# ============================================================
# CONFIG
# ============================================================

COLLECT_INTERVAL = 10

SYMBOL = "gold_18k"

# حداکثر اختلاف قابل قبول بین دو منبع
# به صورت درصد
MAX_SOURCE_DIFFERENCE_PERCENT = 1.0


# ============================================================
# PRICE NORMALIZATION
# ============================================================

def normalize_tgju_price(data):
    """
    تبدیل داده TGJU به ساختار استاندارد سیستم.

    در پروژه ما قیمت نهایی به تومان استفاده می‌شود.
    """

    price = float(
        data["price"]
    )

    currency = str(
        data.get(
            "currency",
            ""
        )
    ).upper()

    # --------------------------------------------------------
    # TGJU فعلی پروژه عملاً قیمت طلای ایران را به تومان
    # برمی‌گرداند، اما currency قبلاً IRR ثبت شده بود.
    #
    # برای جلوگیری از تغییر اشتباه مقدار قیمت،
    # همان عدد را به عنوان تومان در نظر می‌گیریم.
    # --------------------------------------------------------

    if currency in (
        "IRR",
        "RIAL",
        "ریال",
    ):

        price_toman = price

    else:

        price_toman = price

    return {

        "symbol":
            SYMBOL,

        "price":
            int(round(price_toman)),

        "currency":
            "TOMAN",

        "source":
            "tgju",

        "timestamp":
            data.get("timestamp"),
    }


# ============================================================
# SERVIX NORMALIZATION
# ============================================================

def normalize_servix_price(data):
    """
    تبدیل قیمت Servix از ریال به تومان.
    """

    price_riel = float(
        data["price_riel"]
    )

    price_toman = (
        price_riel / 10
    )

    return {

        "symbol":
            SYMBOL,

        "price":
            int(round(price_toman)),

        "currency":
            "TOMAN",

        "source":
            "servix",

        "timestamp":
            data.get(
                "received_at"
            ),

        "business_time":
            data.get(
                "business_time"
            ),
    }


# ============================================================
# SOURCE DIFFERENCE
# ============================================================

def calculate_source_difference(
    price_a,
    price_b
):

    if price_a <= 0:

        return 100.0

    difference = abs(
        price_a - price_b
    )

    percent = (
        difference
        / price_a
    ) * 100

    return percent


# ============================================================
# COLLECT FROM TGJU
# ============================================================

def collect_tgju():

    try:

        print(
            "📡 TGJU: requesting gold price...",
            flush=True
        )

        data = get_gold_18k()

        normalized = normalize_tgju_price(
            data
        )

        print(
            "🟢 TGJU: "
            f"{normalized['price']:,} تومان",
            flush=True
        )

        return normalized

    except Exception as error:

        print(
            "🔴 TGJU ERROR:",
            flush=True
        )

        print(
            f"   {type(error).__name__}: {error}",
            flush=True
        )

        return None


# ============================================================
# COLLECT FROM SERVIX
# ============================================================

def collect_servix():

    try:

        print(
            "📡 SERVIX: requesting gold price...",
            flush=True
        )

        # ----------------------------------------------------
        # Import داخل تابع انجام می‌شود تا SERVIX_API_KEY
        # بعد از load_dotenv خوانده شود.
        # ----------------------------------------------------

        from data.collectors.servix import (
            get_servix_gold
        )

        data = get_servix_gold()

        normalized = normalize_servix_price(
            data
        )

        print(
            "🟢 SERVIX: "
            f"{normalized['price']:,} تومان",
            flush=True
        )

        return normalized

    except Exception as error:

        print(
            "🔴 SERVIX ERROR:",
            flush=True
        )

        print(
            f"   {type(error).__name__}: {error}",
            flush=True
        )

        return None


# ============================================================
# VALIDATE SOURCES
# ============================================================

def validate_sources(
    tgju_data,
    servix_data
):
    """
    انتخاب قیمت معتبر از بین TGJU و Servix.

    حالت‌ها:

    1. هر دو موجود:
       - اختلاف <= 1%:
         میانگین دو منبع
       - اختلاف > 1%:
         TGJU به عنوان قیمت اصلی موقت

    2. فقط TGJU:
       TGJU

    3. فقط Servix:
       Servix

    4. هیچ‌کدام:
       None
    """

    # --------------------------------------------------------
    # NO DATA
    # --------------------------------------------------------

    if (
        tgju_data is None
        and servix_data is None
    ):

        print(
            "❌ VALIDATOR: "
            "No valid source available.",
            flush=True
        )

        return None


    # --------------------------------------------------------
    # TGJU ONLY
    # --------------------------------------------------------

    if (
        tgju_data is not None
        and servix_data is None
    ):

        print(
            "🟡 VALIDATOR: "
            "Using TGJU only.",
            flush=True
        )

        return {

            "symbol":
                SYMBOL,

            "price":
                tgju_data["price"],

            "currency":
                "TOMAN",

            "source":
                "tgju",

            "timestamp":
                tgju_data.get(
                    "timestamp"
                ),
        }


    # --------------------------------------------------------
    # SERVIX ONLY
    # --------------------------------------------------------

    if (
        tgju_data is None
        and servix_data is not None
    ):

        print(
            "🟡 VALIDATOR: "
            "Using Servix only.",
            flush=True
        )

        return {

            "symbol":
                SYMBOL,

            "price":
                servix_data["price"],

            "currency":
                "TOMAN",

            "source":
                "servix",

            "timestamp":
                servix_data.get(
                    "timestamp"
                ),
        }


    # --------------------------------------------------------
    # BOTH SOURCES
    # --------------------------------------------------------

    tgju_price = (
        tgju_data["price"]
    )

    servix_price = (
        servix_data["price"]
    )

    difference_percent = (
        calculate_source_difference(
            tgju_price,
            servix_price
        )
    )

    print(
        "🔎 SOURCE VALIDATION:",
        flush=True
    )

    print(
        f"   TGJU   : {tgju_price:,} تومان",
        flush=True
    )

    print(
        f"   Servix : {servix_price:,} تومان",
        flush=True
    )

    print(
        f"   Difference: "
        f"{difference_percent:.3f}%",
        flush=True
    )


    # --------------------------------------------------------
    # ACCEPTED DIFFERENCE
    # --------------------------------------------------------

    if (
        difference_percent
        <= MAX_SOURCE_DIFFERENCE_PERCENT
    ):

        validated_price = int(
            round(
                (
                    tgju_price
                    + servix_price
                ) / 2
            )
        )

        print(
            "🟢 VALIDATOR: "
            "Sources agree.",
            flush=True
        )

        print(
            f"🟢 VALIDATED PRICE: "
            f"{validated_price:,} تومان",
            flush=True
        )

        return {

            "symbol":
                SYMBOL,

            "price":
                validated_price,

            "currency":
                "TOMAN",

            "source":
                "tgju+servix",

            "timestamp":
                tgju_data.get(
                    "timestamp"
                ),

            "tgju_price":
                tgju_price,

            "servix_price":
                servix_price,

            "source_difference_percent":
                difference_percent,
        }


    # --------------------------------------------------------
    # LARGE DIFFERENCE
    # --------------------------------------------------------

    print(
        "⚠️ VALIDATOR WARNING:",
        flush=True
    )

    print(
        "⚠️ Difference between sources "
        "is higher than allowed threshold.",
        flush=True
    )

    print(
        "⚠️ TGJU selected as temporary "
        "primary source.",
        flush=True
    )

    return {

        "symbol":
            SYMBOL,

        "price":
            tgju_price,

        "currency":
            "TOMAN",

        "source":
            "tgju_warning",

        "timestamp":
            tgju_data.get(
                "timestamp"
            ),

        "tgju_price":
            tgju_price,

        "servix_price":
            servix_price,

        "source_difference_percent":
            difference_percent,
    }


# ============================================================
# COLLECT ONE PRICE
# ============================================================

def collect_once():

    print(
        "",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )

    print(
        "📡 COLLECTOR: New collection cycle",
        flush=True
    )

    print(
        "========================================",
        flush=True
    )


    # --------------------------------------------------------
    # GET BOTH SOURCES
    # --------------------------------------------------------

    tgju_data = collect_tgju()

    servix_data = collect_servix()


    # --------------------------------------------------------
    # VALIDATE
    # --------------------------------------------------------

    data = validate_sources(
        tgju_data,
        servix_data
    )


    if data is None:

        print(
            "❌ COLLECTOR: "
            "No valid price received.",
            flush=True
        )

        return


    # --------------------------------------------------------
    # SAVE VALIDATED PRICE
    # --------------------------------------------------------

    print(
        "💾 COLLECTOR: "
        f"Saving {data['price']:,} تومان "
        f"from {data['source']}",
        flush=True
    )

    save_price(
        data
    )

    print(
        "✅ COLLECTOR: "
        "Validated price saved.",
        flush=True
    )


    # --------------------------------------------------------
    # BUILD 1M CANDLE
    # --------------------------------------------------------

    try:

        candle_1m = build_1m_candle(
            symbol=data["symbol"]
        )

        if candle_1m:

            print(
                "🕯️ COLLECTOR: "
                "1M candle updated.",
                flush=True
            )

    except Exception as error:

        print(
            "❌ COLLECTOR: "
            "1M candle error: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )


    # --------------------------------------------------------
    # BUILD 5M CANDLE
    # --------------------------------------------------------

    try:

        candles_5m = build_timeframe_candles(

            timeframe="5m",

            symbol=data["symbol"],

            limit=500
        )

        if candles_5m:

            print(
                "🕯️ COLLECTOR: "
                "5M candles updated: "
                f"{len(candles_5m)}",
                flush=True
            )

    except Exception as error:

        print(
            "❌ COLLECTOR: "
            "5M candle error: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )


    # --------------------------------------------------------
    # BUILD 15M CANDLE
    # --------------------------------------------------------

    try:

        candles_15m = build_timeframe_candles(

            timeframe="15m",

            symbol=data["symbol"],

            limit=500
        )

        if candles_15m:

            print(
                "🕯️ COLLECTOR: "
                "15M candles updated: "
                f"{len(candles_15m)}",
                flush=True
            )

    except Exception as error:

        print(
            "❌ COLLECTOR: "
            "15M candle error: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )


    # --------------------------------------------------------
    # BUILD 1H CANDLE
    # --------------------------------------------------------

    try:

        candles_1h = build_timeframe_candles(

            timeframe="1h",

            symbol=data["symbol"],

            limit=500
        )

        if candles_1h:

            print(
                "🕯️ COLLECTOR: "
                "1H candles updated: "
                f"{len(candles_1h)}",
                flush=True
            )

    except Exception as error:

        print(
            "❌ COLLECTOR: "
            "1H candle error: "
            f"{type(error).__name__}: "
            f"{error}",
            flush=True
        )


    print(
        "✅ COLLECTOR: "
        "Collection cycle finished.",
        flush=True
    )


# ============================================================
# COLLECTOR LOOP
# ============================================================

def run_collector():

    print(
        "🤖 COLLECTOR SERVICE STARTED",
        flush=True
    )

    print(
        f"⏱️ Collection interval: "
        f"{COLLECT_INTERVAL} seconds",
        flush=True
    )

    print(
        "📊 Timeframes: "
        "1m / 5m / 15m / 1h",
        flush=True
    )

    print(
        "📡 Sources: "
        "TGJU + Servix",
        flush=True
    )

    print(
        f"⚖️ Maximum source difference: "
        f"{MAX_SOURCE_DIFFERENCE_PERCENT}%",
        flush=True
    )


    while True:

        try:

            collect_once()

        except Exception as error:

            print(
                "❌ COLLECTOR ERROR:",
                flush=True
            )

            print(
                f"Type: {type(error).__name__}",
                flush=True
            )

            print(
                f"Message: {error}",
                flush=True
            )

            traceback.print_exc()


        print(
            f"⏳ COLLECTOR: Waiting "
            f"{COLLECT_INTERVAL} seconds...",
            flush=True
        )

        time.sleep(
            COLLECT_INTERVAL
        )


# ============================================================
# DIRECT EXECUTION
# ============================================================

if __name__ == "__main__":

    run_collector()
