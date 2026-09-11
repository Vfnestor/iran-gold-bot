import os
import threading

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

from database import (
    init_db,
    save_price,
    get_latest_prices,
)

from candle_engine import build_1m_candle


# ============================================================
# LOAD ENVIRONMENT
# ============================================================

load_dotenv()

print(
    "DEBUG 1: main.py started",
    flush=True
)


# ============================================================
# ENV VARIABLES
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")


# ============================================================
# HEALTH CHECK SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-type",
            "text/plain; charset=utf-8"
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI is running."
        )

    def log_message(self, format, *args):
        return


def start_health_server():

    port = int(
        os.environ.get(
            "PORT",
            10000
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


# ============================================================
# TELEGRAM KEYBOARD
# ============================================================

def main_keyboard():

    keyboard = [

        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 وضعیت بازار"),
        ],

        [
            KeyboardButton("📈 کندل 1 دقیقه"),
            KeyboardButton("📉 تحلیل"),
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

        "🤖 Iran Gold AI\n\n"
        "به ربات تحلیل هوشمند بازار طلا خوش آمدید.\n\n"
        "یک گزینه را انتخاب کنید:",

        reply_markup=main_keyboard()
    )


# ============================================================
# PRICE COMMAND
# ============================================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        data = get_gold_18k()

        save_price(data)

        price = data["price"]

        source = data.get(
            "source",
            "TGJU"
        )

        message = (

            "🟡 قیمت لحظه‌ای طلای ۱۸ عیار\n\n"

            f"💰 قیمت: {price:,.0f} تومان\n"

            f"📡 منبع: {source}\n"

        )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            f"❌ PRICE COMMAND ERROR: {error}",
            flush=True
        )

        await update.message.reply_text(

            "❌ دریافت قیمت با خطا مواجه شد.\n"
            "لطفاً چند لحظه بعد دوباره تلاش کنید."

        )


# ============================================================
# MARKET STATUS
# ============================================================

async def market_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        prices = get_latest_prices()

        if not prices:

            await update.message.reply_text(
                "⚠️ هنوز داده‌ای در دیتابیس ثبت نشده است."
            )

            return

        message = "📊 وضعیت بازار\n\n"

        for item in prices:

            message += (
                f"📡 {item}\n"
            )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            f"❌ MARKET STATUS ERROR: {error}",
            flush=True
        )

        await update.message.reply_text(
            "❌ دریافت وضعیت بازار ناموفق بود."
        )


# ============================================================
# CANDLE COMMAND
# ============================================================

async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        candle = build_1m_candle()

        if not candle:

            await update.message.reply_text(
                "⚠️ هنوز اطلاعات کافی برای ساخت کندل وجود ندارد."
            )

            return

        message = (

            "📈 کندل ۱ دقیقه‌ای\n\n"

            f"🟢 Open: {candle['open']:,.0f}\n"
            f"🔵 High: {candle['high']:,.0f}\n"
            f"🔴 Low: {candle['low']:,.0f}\n"
            f"⚪ Close: {candle['close']:,.0f}\n"

        )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            f"❌ CANDLE ERROR: {error}",
            flush=True
        )

        await update.message.reply_text(
            "❌ ساخت کندل با خطا مواجه شد."
        )


# ============================================================
# ANALYSIS COMMAND
# ============================================================

async def analysis_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🧠 موتور تحلیل Iran Gold AI\n\n"
        "⏳ بخش تحلیل در حال توسعه است."

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

    elif text == "📊 وضعیت بازار":

        await market_status_command(
            update,
            context
        )

    elif text == "📈 کندل 1 دقیقه":

        await candle_command(
            update,
            context
        )

    elif text == "📉 تحلیل":

        await analysis_command(
            update,
            context
        )

    else:

        await update.message.reply_text(

            "❓ دستور موردنظر را انتخاب کنید.",

            reply_markup=main_keyboard()
        )


# ============================================================
# SERVIX TEST
# ============================================================

def test_servix():

    print(
        "🧪 SERVIX: starting test...",
        flush=True
    )

    try:

        from data.collectors.servix import get_servix_gold

        print(
            "✅ SERVIX MODULE: imported successfully",
            flush=True
        )

        servix_data = get_servix_gold()

        print(
            "✅ SERVIX: API connection successful",
            flush=True
        )

        print(
            f"📡 SERVIX SOURCE: "
            f"{servix_data['source']}",
            flush=True
        )

        print(
            f"🪙 SERVIX SYMBOL: "
            f"{servix_data['symbol']}",
            flush=True
        )

        print(
            f"💰 SERVIX PRICE RIAL: "
            f"{servix_data['price_riel']:,}",
            flush=True
        )

        print(
            f"💵 SERVIX PRICE TOMAN: "
            f"{servix_data['price_toman']:,}",
            flush=True
        )

        print(
            f"🕐 SERVIX BUSINESS TIME: "
            f"{servix_data['business_time']}",
            flush=True
        )

    except Exception as error:

        print(
            "❌ SERVIX TEST FAILED",
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


# ============================================================
# MAIN
# ============================================================

def main():

    print(
        "🚀 Starting Iran Gold AI...",
        flush=True
    )

    # --------------------------------------------------------
    # CHECK BOT TOKEN
    # --------------------------------------------------------

    if not BOT_TOKEN:

        print(
            "❌ BOT_TOKEN environment variable is missing.",
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
            "❌ DATABASE INITIALIZATION FAILED",
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

        return

    # --------------------------------------------------------
    # SERVIX TEST
    # --------------------------------------------------------

    test_servix()

    # --------------------------------------------------------
    # HEALTH SERVER
    # --------------------------------------------------------

    try:

        health_thread = threading.Thread(
            target=start_health_server,
            daemon=True
        )

        health_thread.start()

        print(
            "🌐 Health server thread started.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ HEALTH SERVER FAILED",
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

    # --------------------------------------------------------
    # COLLECTOR
    # --------------------------------------------------------

    try:

        collector_thread = threading.Thread(
            target=run_collector,
            daemon=True
        )

        collector_thread.start()

        print(
            "📡 Collector started.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ COLLECTOR START FAILED",
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

    # --------------------------------------------------------
    # TELEGRAM APPLICATION
    # --------------------------------------------------------

    try:

        application = (
            Application.builder()
            .token(BOT_TOKEN)
            .build()
        )

        print(
            "🤖 Telegram application created.",
            flush=True
        )

    except Exception as error:

        print(
            "❌ TELEGRAM APPLICATION FAILED",
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

        return

    # --------------------------------------------------------
    # HANDLERS
    # --------------------------------------------------------

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
        "✅ Telegram handlers registered.",
        flush=True
    )

    # --------------------------------------------------------
    # START BOT
    # --------------------------------------------------------

    print(
        "🤖 Telegram bot starting...",
        flush=True
    )

    try:

        application.run_polling()

    except Exception as error:

        print(
            "❌ TELEGRAM POLLING FAILED",
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


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    main()
