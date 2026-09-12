import os
import threading
import traceback
import time

from dotenv import load_dotenv

from telegram import (
    Update,
    ReplyKeyboardMarkup,
    KeyboardButton,
)

from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from http.server import BaseHTTPRequestHandler, HTTPServer

from data.collector_service import run_collector
from data.collectors.tgju import get_gold_18k
from data.collectors.world_gold import get_world_gold
from data.collectors.usd_toman import get_usd_toman

from database import (
    init_db,
    get_latest_market_snapshot,
    get_analysis_history,
    get_latest_analysis,
)

from candle_engine import (
    get_recent_candles,
)

from analysis_engine import (
    run_analysis,
    format_analysis_summary,
)


# ============================================================
# ENV
# ============================================================

load_dotenv()

print(
    "DEBUG 1: main.py started",
    flush=True
)


# ============================================================
# CONFIG
# ============================================================

ANALYSIS_INTERVAL = 5 * 60


# ============================================================
# TGJU PRICE NORMALIZER
# ============================================================

def get_tgju_toman(data):

    if data.get("price_toman") is not None:

        return float(
            data["price_toman"]
        )

    price = float(
        data["price"]
    )

    currency = str(
        data.get(
            "currency",
            ""
        )
    ).upper()

    if currency in (
        "IRR",
        "RLS",
        "RIAL",
        "ریال",
    ):

        return price / 10

    if price > 100_000_000:

        return price / 10

    return price


# ============================================================
# TEST ALL SOURCES
# ============================================================

def test_all_sources():

    results = []

    # ========================================================
    # TGJU
    # ========================================================

    try:

        print(
            "🧪 TGJU: starting test...",
            flush=True
        )

        tgju_data = get_gold_18k()

        tgju_price_toman = get_tgju_toman(
            tgju_data
        )

        results.append({
            "name": "TGJU",
            "ok": True,
            "message": (
                f"💰 {tgju_price_toman:,.0f} تومان"
            ),
        })

        print(
            f"✅ TGJU: "
            f"{tgju_price_toman:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ TGJU TEST FAILED: {error}",
            flush=True
        )

        results.append({
            "name": "TGJU",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # SERVIX
    # ========================================================

    try:

        print(
            "🧪 SERVIX: starting test...",
            flush=True
        )

        from data.collectors.servix import (
            get_servix_gold
        )

        servix_data = get_servix_gold()

        servix_price_toman = float(
            servix_data["price_toman"]
        )

        results.append({
            "name": "Servix",
            "ok": True,
            "message": (
                f"💰 {servix_price_toman:,.0f} تومان"
            ),
        })

        print(
            f"✅ SERVIX: "
            f"{servix_price_toman:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ SERVIX TEST FAILED: {error}",
            flush=True
        )

        results.append({
            "name": "Servix",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # WORLD GOLD
    # ========================================================

    try:

        print(
            "🧪 WORLD GOLD: starting test...",
            flush=True
        )

        world_data = get_world_gold()

        world_price = float(
            world_data["price_usd"]
        )

        results.append({
            "name": "World Gold",
            "ok": True,
            "message": (
                f"🌎 ${world_price:,.2f} / oz"
            ),
        })

        print(
            f"✅ WORLD GOLD: "
            f"${world_price:,.2f} / oz",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ WORLD GOLD TEST FAILED: {error}",
            flush=True
        )

        results.append({
            "name": "World Gold",
            "ok": False,
            "message": str(error),
        })

    # ========================================================
    # USD / TOMAN
    # ========================================================

    try:

        print(
            "🧪 USD/TOMAN: starting test...",
            flush=True
        )

        usd_data = get_usd_toman()

        usd_mid = float(
            usd_data.get(
                "mid",
                usd_data.get(
                    "mid_toman"
                )
            )
        )

        usd_buy = float(
            usd_data.get(
                "buy",
                usd_data.get(
                    "buy_toman"
                )
            )
        )

        usd_sell = float(
            usd_data.get(
                "sell",
                usd_data.get(
                    "sell_toman"
                )
            )
        )

        results.append({
            "name": "USD/Toman",
            "ok": True,
            "message": (
                f"💵 Mid: {usd_mid:,.0f} تومان\n"
                f"   خرید: {usd_buy:,.0f}\n"
                f"   فروش: {usd_sell:,.0f}"
            ),
        })

        print(
            f"✅ USD/TOMAN: "
            f"{usd_mid:,.0f} تومان",
            flush=True
        )

    except Exception as error:

        print(
            f"❌ USD/TOMAN TEST FAILED: {error}",
            flush=True
        )

        results.append({
            "name": "USD/Toman",
            "ok": False,
            "message": str(error),
        })

    return results


# ============================================================
# TELEGRAM SOURCE TEST
# ============================================================

async def source_test_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🧪 در حال بررسی منابع...\n\n"
        "لطفاً چند ثانیه صبر کنید."
    )

    try:

        results = test_all_sources()

        lines = [
            "🧪 نتیجه تست منابع",
            "",
        ]

        online_count = 0

        for result in results:

            if result["ok"]:

                online_count += 1

                lines.append(
                    f"🟢 {result['name']}"
                )

                lines.append(
                    f"   {result['message']}"
                )

            else:

                lines.append(
                    f"🔴 {result['name']}"
                )

                lines.append(
                    f"   ⚠️ {result['message']}"
                )

            lines.append("")

        lines.append(
            "━━━━━━━━━━━━━━━━"
        )

        lines.append(
            f"📊 وضعیت: "
            f"{online_count}/{len(results)} منبع فعال"
        )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:

        print(
            "❌ SOURCE TEST COMMAND ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا هنگام تست منابع."
        )


# ============================================================
# HEALTH CHECK SERVER
# ============================================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI is running."
        )

    def log_message(
        self,
        format,
        *args
    ):

        return


def start_health_server():

    try:

        port = int(
            os.getenv(
                "PORT",
                "10000"
            )
        )

        server = HTTPServer(
            ("0.0.0.0", port),
            HealthHandler
        )

        print(
            f"🌐 Health server running on port {port}",
            flush=True
        )

        server.serve_forever()

    except Exception as error:

        print(
            "❌ Health server failed:",
            error,
            flush=True
        )


# ============================================================
# TELEGRAM MENU
# ============================================================

def get_main_keyboard():

    keyboard = [
        [
            KeyboardButton(
                "🟡 قیمت لحظه‌ای"
            ),
            KeyboardButton(
                "📊 تاریخچه"
            ),
        ],
        [
            KeyboardButton(
                "📈 کندل‌ها"
            ),
            KeyboardButton(
                "🧠 تحلیل"
            ),
        ],
        [
            KeyboardButton(
                "🧪 تست منابع"
            ),
            KeyboardButton(
                "ℹ️ درباره"
            ),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )


# ============================================================
# START COMMAND
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 به Iran Gold AI خوش آمدید.\n\n"
        "سیستم هوشمند تحلیل بازار طلای ایران.\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=get_main_keyboard()
    )


# ============================================================
# PRICE COMMAND
# ============================================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        snapshot = (
            get_latest_market_snapshot()
        )

        if snapshot:

            price = snapshot.get(
                "gold_18k_toman"
            )

            timestamp = snapshot.get(
                "timestamp",
                ""
            )

            if price is not None:

                await update.message.reply_text(
                    "🟡 قیمت لحظه‌ای طلای ۱۸ عیار\n\n"
                    f"💰 قیمت: "
                    f"{float(price):,.0f} تومان\n"
                    "📡 منبع: TGJU\n"
                    f"🕐 زمان: {timestamp}"
                )

                return

        # ----------------------------------------------------
        # FALLBACK
        # ----------------------------------------------------

        data = get_gold_18k()

        price = get_tgju_toman(
            data
        )

        source = data.get(
            "source",
            "TGJU"
        )

        await update.message.reply_text(
            "🟡 قیمت لحظه‌ای طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,.0f} تومان\n"
            f"📡 منبع: {source}"
        )

    except Exception as error:

        print(
            "❌ PRICE COMMAND ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت قیمت."
        )


# ============================================================
# HISTORY COMMAND
# ============================================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        analyses = get_analysis_history(
            limit=10
        )

        if not analyses:

            await update.message.reply_text(
                "📊 هنوز تحلیل ثبت‌شده‌ای "
                "در دیتابیس وجود ندارد.\n\n"
                "بعد از جمع شدن داده کافی، "
                "تاریخچه تحلیل‌ها اینجا نمایش داده می‌شود."
            )

            return

        lines = [
            "📊 تاریخچه تحلیل‌های Iran Gold AI",
            "",
        ]

        for index, item in enumerate(
            analyses,
            start=1
        ):

            price = item.get(
                "price_toman"
            )

            confidence = item.get(
                "confidence"
            )

            signal = item.get(
                "signal",
                "HOLD"
            )

            trend = item.get(
                "trend",
                "خنثی"
            )

            timestamp = item.get(
                "timestamp",
                ""
            )

            price_text = (
                f"{float(price):,.0f} تومان"
                if price is not None
                else "نامشخص"
            )

            confidence_text = (
                f"{float(confidence):.0f}%"
                if confidence is not None
                else "—"
            )

            lines.append(
                f"{index}. "
                f"💰 {price_text}\n"
                f"   🎯 {signal} | "
                f"📈 {trend} | "
                f"📊 {confidence_text}\n"
                f"   🕐 {timestamp}"
            )

            lines.append(
                "━━━━━━━━━━━━━━━━"
            )

        await update.message.reply_text(
            "\n".join(lines)
        )

    except Exception as error:

        print(
            "❌ HISTORY ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت تاریخچه تحلیل."
        )


# ============================================================
# CANDLE COMMAND
# ============================================================

async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        messages = []

        for timeframe in (
            "5m",
            "15m",
            "1h",
        ):

            candles = get_recent_candles(
                timeframe=timeframe,
                limit=1
            )

            if not candles:

                messages.append(
                    f"🕯️ {timeframe}: "
                    "هنوز کندلی وجود ندارد."
                )

                continue

            candle = candles[0]

            open_price = candle.get(
                "open"
            )

            high_price = candle.get(
                "high"
            )

            low_price = candle.get(
                "low"
            )

            close_price = candle.get(
                "close"
            )

            messages.append(
                f"🕯️ کندل {timeframe}\n"
                f"   O: {float(open_price):,.0f}\n"
                f"   H: {float(high_price):,.0f}\n"
                f"   L: {float(low_price):,.0f}\n"
                f"   C: {float(close_price):,.0f}"
            )

        await update.message.reply_text(
            "📈 آخرین کندل‌ها\n\n"
            + "\n\n".join(messages)
        )

    except Exception as error:

        print(
            "❌ CANDLE COMMAND ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در دریافت کندل‌ها."
        )


# ============================================================
# ANALYSIS COMMAND
# ============================================================

async def analysis_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🧠 در حال انجام تحلیل بازار...\n\n"
        "لطفاً چند ثانیه صبر کنید."
    )

    try:

        analysis = run_analysis()

        if not analysis:

            await update.message.reply_text(
                "⚠️ هنوز داده کافی برای تحلیل وجود ندارد.\n\n"
                "سیستم باید ابتدا چند کندل ۵ دقیقه‌ای "
                "جمع‌آوری کند."
            )

            return

        message = format_analysis_summary(
            analysis
        )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            "❌ ANALYSIS COMMAND ERROR:",
            error,
            flush=True
        )

        traceback.print_exc()

        await update.message.reply_text(
            "❌ خطا در انجام تحلیل."
        )


# ============================================================
# ABOUT COMMAND
# ============================================================

async def about_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🤖 Iran Gold AI\n\n"

        "سیستم هوشمند جمع‌آوری، "
        "اعتبارسنجی و تحلیل قیمت طلای ایران.\n\n"

        "📡 منابع داده\n"
        "• TGJU\n"
        "• Servix\n"
        "• World Gold API\n"
        "• NetArz USD/Toman\n\n"

        "🌎 داده جهانی\n"
        "• XAU/USD\n"
        "• قیمت هر اونس تروا\n\n"

        "💵 داده ارزی\n"
        "• دلار / تومان\n"
        "• نرخ خرید\n"
        "• نرخ فروش\n"
        "• نرخ میانگین\n\n"

        "🔄 جمع‌آوری بازار\n"
        "• هر ۵ دقیقه\n"
        "• ذخیره Market Snapshot\n"
        "• ساخت کندل ۵ دقیقه‌ای\n"
        "• ساخت کندل ۱۵ دقیقه‌ای\n"
        "• ساخت کندل ۱ ساعته\n\n"

        "🧠 موتور تحلیل\n"
        "• EMA\n"
        "• RSI\n"
        "• MACD\n"
        "• ATR\n"
        "• Momentum\n"
        "• Support / Resistance\n"
        "• Fair Value\n"
        "• Trend\n"
        "• Signal\n"
        "• Confidence\n"
        "• Entry / SL / TP\n\n"

        "🗄️ وضعیت سیستم\n"
        "• دیتابیس: فعال\n"
        "• جمع‌آوری داده: فعال\n"
        "• موتور کندل: فعال\n"
        "• موتور تحلیل: فعال\n\n"

        "🚀 هدف Iran Gold AI:\n"
        "ارائه تحلیل داده‌محور و قابل اعتماد "
        "برای بازار طلای ایران.\n\n"

        "❤️ تقدیم به دختر عزیزم، پناه"
    )


# ============================================================
# TEXT HANDLER
# ============================================================

async def text_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    if text == "🟡 قیمت لحظه‌ای":

        await price_command(
            update,
            context
        )

    elif text == "📊 تاریخچه":

        await history_command(
            update,
            context
        )

    elif text == "📈 کندل‌ها":

        await candle_command(
            update,
            context
        )

    elif text == "🧠 تحلیل":

        await analysis_command(
            update,
            context
        )

    elif text == "🧪 تست منابع":

        await source_test_command(
            update,
            context
        )

    elif text == "ℹ️ درباره":

        await about_command(
            update,
            context
        )

    else:

        await update.message.reply_text(
            "❓ دستور موردنظر را از منوی پایین انتخاب کنید."
        )


# ============================================================
# COLLECTOR THREAD
# ============================================================

def start_collector():

    print(
        "🚀 COLLECTOR THREAD: starting...",
        flush=True
    )

    try:

        run_collector()

    except Exception as error:

        print(
            "❌ COLLECTOR THREAD FAILED",
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


# ============================================================
# ANALYSIS THREAD
# ============================================================

def start_analysis_engine():

    print(
        "🧠 ANALYSIS THREAD: starting...",
        flush=True
    )

    while True:

        try:

            analysis = run_analysis()

            if analysis:

                print(
                    "🧠 Scheduled analysis saved.",
                    flush=True
                )

            else:

                print(
                    "ℹ️ Scheduled analysis skipped "
                    "(not enough data yet).",
                    flush=True
                )

        except Exception as error:

            print(
                "❌ ANALYSIS THREAD ERROR:",
                error,
                flush=True
            )

            traceback.print_exc()

        time.sleep(
            ANALYSIS_INTERVAL
        )


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "🚀 Starting Iran Gold AI...",
        flush=True
    )

    # --------------------------------------------------------
    # BOT TOKEN
    # --------------------------------------------------------

    bot_token = os.getenv(
        "BOT_TOKEN"
    )

    if not bot_token:

        print(
            "❌ BOT_TOKEN not found.",
            flush=True
        )

        return

    print(
        "✅ BOT_TOKEN found.",
        flush=True
    )

    # --------------------------------------------------------
    # DATABASE
    # --------------------------------------------------------

    try:

        init_db()

        print(
            "🗄️ Database initialized.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Database initialization failed:",
            error,
            flush=True
        )

        traceback.print_exc()

        return

    # --------------------------------------------------------
    # SERVIX STARTUP TEST DISABLED
    # --------------------------------------------------------

    print(
        "ℹ️ SERVIX startup test disabled.",
        flush=True
    )

    # --------------------------------------------------------
    # HEALTH SERVER
    # --------------------------------------------------------

    health_thread = threading.Thread(
        target=start_health_server,
        daemon=True
    )

    health_thread.start()

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

    try:

        application = (
            Application
            .builder()
            .token(bot_token)
            .build()
        )

        application.add_handler(
            CommandHandler(
                "start",
                start_command
            )
        )

        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND,
                text_handler
            )
        )

        print(
            "✅ Telegram application initialized.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ Telegram application initialization failed:",
            error,
            flush=True
        )

        traceback.print_exc()

        return

    # --------------------------------------------------------
    # COLLECTOR
    # --------------------------------------------------------

    collector_thread = threading.Thread(
        target=start_collector,
        daemon=True
    )

    collector_thread.start()

    print(
        "🟢 Collector thread started.",
        flush=True
    )

    # --------------------------------------------------------
    # ANALYSIS
    # --------------------------------------------------------

    analysis_thread = threading.Thread(
        target=start_analysis_engine,
        daemon=True
    )

    analysis_thread.start()

    print(
        "🧠 Analysis thread started.",
        flush=True
    )

    # --------------------------------------------------------
    # TELEGRAM POLLING
    # --------------------------------------------------------

    print(
        "📡 Starting Telegram polling...",
        flush=True
    )

    try:

        application.run_polling(
            drop_pending_updates=True
        )

    except Exception as error:

        print(
            "❌ Telegram polling failed.",
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


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
