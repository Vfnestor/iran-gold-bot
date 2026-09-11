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


# ==========================================
# Environment
# ==========================================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

PORT = int(
    os.getenv("PORT", "10000")
)


# ==========================================
# Telegram Keyboard
# ==========================================

def get_main_keyboard():

    keyboard = [
        [
            KeyboardButton("🟡 قیمت لحظه‌ای"),
            KeyboardButton("📊 تاریخچه"),
        ],
        [
            KeyboardButton("🔄 بروزرسانی"),
            KeyboardButton("ℹ️ راهنما"),
        ],
    ]

    return ReplyKeyboardMarkup(
        keyboard,
        resize_keyboard=True,
        one_time_keyboard=False,
    )


# ==========================================
# Health Server
# ==========================================

class HealthHandler(
    BaseHTTPRequestHandler
):

    def do_GET(self):

        self.send_response(200)

        self.send_header(
            "Content-Type",
            "text/plain"
        )

        self.end_headers()

        self.wfile.write(
            b"Iran Gold AI Bot is running."
        )

    def log_message(
        self,
        format,
        *args
    ):

        return


def run_health_server():

    server = HTTPServer(
        (
            "0.0.0.0",
            PORT
        ),
        HealthHandler
    )

    print(
        f"🌐 Health server running "
        f"on port {PORT}"
    )

    server.serve_forever()


# ==========================================
# /start
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n\n"
        "📊 سیستم جمع‌آوری قیمت طلای ایران فعال است.\n\n"
        "📡 داده‌ها به صورت خودکار "
        "جمع‌آوری می‌شوند.\n\n"
        "👇 از منوی زیر استفاده کن.",

        reply_markup=get_main_keyboard()
    )


# ==========================================
# /help
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(

        "ℹ️ راهنمای Iran Gold AI\n\n"

        "🟡 قیمت لحظه‌ای\n"
        "آخرین قیمت طلای ۱۸ عیار\n\n"

        "📊 تاریخچه\n"
        "آخرین داده‌های ذخیره‌شده\n\n"

        "🔄 بروزرسانی\n"
        "دریافت دستی قیمت جدید\n\n"

        "ℹ️ راهنما\n"
        "نمایش راهنما\n\n"

        "🔮 مراحل آینده:\n"
        "• نمودار قیمت\n"
        "• کندل‌های چندبازه‌ای\n"
        "• RSI\n"
        "• MACD\n"
        "• حمایت و مقاومت\n"
        "• مناطق احتمالی خرید\n"
        "• اهداف هفته\n"
        "• اهداف ماه\n"
        "• اهداف سال",

        reply_markup=get_main_keyboard()
    )


# ==========================================
# Manual Price
# ==========================================

async def price_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        print(
            "👤 MANUAL: Price requested"
        )

        data = get_gold_18k()

        save_price(data)

        print(
            "💾 MANUAL: Price saved."
        )

        # ------------------------------
        # Update 1M Candle
        # ------------------------------

        try:

            candle = build_1m_candle(
                symbol=data["symbol"]
            )

            if candle:

                print(
                    "🕯️ MANUAL: "
                    "1M candle updated."
                )

        except Exception as error:

            print(
                "❌ MANUAL CANDLE ERROR: "
                f"{type(error).__name__}: "
                f"{error}"
            )

        price = data["price"]

        await update.message.reply_text(

            "🟡 طلای ۱۸ عیار\n\n"

            f"💰 قیمت: "
            f"{price:,} ریال\n"

            f"📡 منبع: "
            f"{data['source']}\n"

            f"🕐 زمان: "
            f"{data['timestamp']}",

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ MANUAL PRICE ERROR: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        await update.message.reply_text(

            "❌ در دریافت قیمت مشکلی پیش آمد.\n\n"

            f"{type(error).__name__}: "
            f"{error}",

            reply_markup=get_main_keyboard()
        )


# ==========================================
# History
# ==========================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        rows = get_latest_prices(10)

        if not rows:

            await update.message.reply_text(

                "📭 هنوز هیچ قیمتی "
                "در دیتابیس ذخیره نشده است.",

                reply_markup=get_main_keyboard()
            )

            return

        message = (
            "📊 آخرین قیمت‌های ثبت‌شده\n\n"
        )

        for index, row in enumerate(
            rows,
            start=1
        ):

            price = row[0]

            currency = row[1]

            source = row[2]

            timestamp = row[3]

            message += (

                f"{index}. "
                f"💰 {price:,} {currency}\n"

                f"   📡 {source}\n"

                f"   🕐 {timestamp}\n\n"
            )

        await update.message.reply_text(

            message,

            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            "❌ HISTORY ERROR: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        await update.message.reply_text(

            "❌ خطا در خواندن تاریخچه:\n\n"

            f"{type(error).__name__}: "
            f"{error}",

            reply_markup=get_main_keyboard()
        )


# ==========================================
# Button Handler
# ==========================================

async def menu_handler(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    text = update.message.text

    print(
        f"🔘 BUTTON PRESSED: {text}"
    )

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

    elif text == "🔄 بروزرسانی":

        await price_command(
            update,
            context
        )

    elif text == "ℹ️ راهنما":

        await help_command(
            update,
            context
        )

    else:

        await update.message.reply_text(

            "🤔 این گزینه را متوجه نشدم.\n"
            "لطفاً از دکمه‌های منو استفاده کن.",

            reply_markup=get_main_keyboard()
        )


# ==========================================
# Main
# ==========================================

def main():

    if not BOT_TOKEN:

        raise RuntimeError(
            "BOT_TOKEN is not configured."
        )

    # ======================================
    # Database
    # ======================================

    init_db()

    # ======================================
    # Health Server
    # ======================================

    health_thread = threading.Thread(

        target=run_health_server,

        daemon=True
    )

    health_thread.start()

    # ======================================
    # Collector Service
    # ======================================

    collector_thread = threading.Thread(

        target=run_collector,

        daemon=True
    )

    collector_thread.start()

    # ======================================
    # Telegram
    # ======================================

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ======================================
    # Commands
    # ======================================

    application.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    application.add_handler(
        CommandHandler(
            "help",
            help_command
        )
    )

    application.add_handler(
        CommandHandler(
            "price",
            price_command
        )
    )

    application.add_handler(
        CommandHandler(
            "history",
            history_command
        )
    )

    # ======================================
    # Buttons
    # ======================================

    application.add_handler(

        MessageHandler(

            filters.TEXT
            & ~filters.COMMAND,

            menu_handler
        )
    )

    print(
        "🤖 Iran Gold AI Bot is running..."
    )

    application.run_polling()


# ==========================================
# Entry Point
# ==========================================

if __name__ == "__main__":

    main()
