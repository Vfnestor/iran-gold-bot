import time

from data.collectors.tgju import get_gold_18k

from database import save_price

from candle_engine import (
    build_1m_candle,
    build_timeframe_candles,
)


# ============================================================
# CONFIG
# ============================================================

COLLECT_INTERVAL = 10

SYMBOL = "gold_18k"


# ============================================================
# COLLECT ONE PRICE
# ============================================================

def collect_once():

    print(
        "📡 COLLECTOR: Requesting price from TGJU...",
        flush=True
    )

    # --------------------------------------------------------
    # GET DATA
    # --------------------------------------------------------

    data = get_gold_18k()

    print(
        "📥 COLLECTOR: Price received: "
        f"{data['price']:,} "
        f"{data['currency']}",
        flush=True
    )

    # --------------------------------------------------------
    # SAVE RAW PRICE
    # --------------------------------------------------------

    save_price(
        data
    )

    print(
        "💾 COLLECTOR: Raw price saved.",
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

    while True:

        try:

            collect_once()

        except Exception as error:

            print(
                "❌ COLLECTOR ERROR: "
                f"{type(error).__name__}: "
                f"{error}",
                flush=True
            )

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
