import os
import threading
import traceback

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
# ENV
# ============================================================

load_dotenv()

print("DEBUG 1: main.py started", flush=True)


# ============================================================
# SERVIX TEST
# ============================================================

def test_servix():

    print("🧪 SERVIX: starting test...", flush=True)

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

        return True

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

        traceback.print_exc()

        return False


# ============================================================
# HEALTH CHECK SERVER
# ============================================================

class HealthHandler(BaseHTTPRequestHandler):

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

    def log_message(self, format, *args):
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
# TELEGRAM COMMANDS
# ============================================================

async def start_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    keyboard = [
        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 تاریخچه"),
        ],
        [
            KeyboardButton("📈 کندل‌ها"),
            KeyboardButton("ℹ️ درباره"),
        ],
    ]

    reply_markup = ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True
    )

    await update.message.reply_text(
        "🤖 به Iran Gold AI خوش آمدید.\n\n"
        "یک گزینه را انتخاب کنید:",
        reply_markup=reply_markup
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
            "unknown"
        )

        message = (
            "🟡 قیمت لحظه‌ای طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,} تومان\n"
            f"📡 منبع: {source}"
        )

        await update.message.reply_text(
            message
        )

    except Exception as error:

        print(
            "❌ PRICE COMMAND ERROR:",
            error,
            flush=True
        )

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

        prices = get_latest_prices(10)

        if not prices:

            await update.message.reply_text(
                "📊 هنوز داده‌ای در دیتابیس وجود ندارد."
            )

            return

        lines = [
            "📊 آخرین قیمت‌های ثبت‌شده:",
            ""
        ]

        for item in prices:

            try:

                price = item["price"]

                timestamp = item.get(
                    "timestamp",
                    ""
                )

                lines.append(
                    f"💰 {price:,} | {timestamp}"
                )

            except Exception:

                lines.append(
                    str(item)
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

        await update.message.reply_text(
            "❌ خطا در دریافت تاریخچه."
        )


# ============================================================
# CANDLE COMMAND
# ============================================================

async def candle_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        candles = build_1m_candle()

        if not candles:

            await update.message.reply_text(
                "🕯️ هنوز کندلی ساخته نشده است."
            )

            return

        await update.message.reply_text(
            f"🕯️ تعداد کندل‌های ۱ دقیقه‌ای: "
            f"{len(candles)}"
        )

    except Exception as error:

        print(
            "❌ CANDLE COMMAND ERROR:",
            error,
            flush=True
        )

        await update.message.reply_text(
            "❌ خطا در دریافت کندل‌ها."
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
        "• Servix\n\n"

        "🔄 داده‌ها به‌صورت دوره‌ای "
        "دریافت و بررسی می‌شوند.\n\n"

        "🕯️ موتور تحلیل\n"
        "• کندل ۱ دقیقه‌ای\n"
        "• کندل ۵ دقیقه‌ای\n"
        "• کندل ۱۵ دقیقه‌ای\n"
        "• کندل ۱ ساعته\n\n"

        "🗄️ وضعیت سیستم\n"
        "• دیتابیس: فعال\n"
        "• جمع‌آوری داده: فعال\n"
        "• موتور کندل: فعال\n"
        "• اعتبارسنجی چندمنبعی: در حال توسعه\n\n"

        "🚀 هدف Iran Gold AI:\n"
        "ارائه داده‌های دقیق و قابل اعتماد "
        "برای تحلیل بازار طلای ایران.\n\n"

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
    # SERVIX TEST
    # --------------------------------------------------------

    servix_ok = test_servix()

    if servix_ok:

        print(
            "🟢 SERVIX STATUS: ONLINE",
            flush=True
        )

    else:

        print(
            "🔴 SERVIX STATUS: OFFLINE",
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
