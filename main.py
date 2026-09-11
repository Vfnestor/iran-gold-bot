import os
import threading
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

from data.collectors.tgju import get_gold_18k

from database import (
    init_db,
    save_price,
    get_latest_prices,
)

from candle_engine import build_1m_candle


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
PORT = int(os.getenv("PORT", "10000"))

# ==========================================
# Automatic Collector
# ==========================================

# فعلاً هر 60 ثانیه یک بار قیمت دریافت می‌شود.
COLLECT_INTERVAL = 60


# ==========================================
# Main Keyboard
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
# Render Health Server
# ==========================================

class HealthHandler(BaseHTTPRequestHandler):

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

    def log_message(self, format, *args):
        return


def run_health_server():

    server = HTTPServer(
        ("0.0.0.0", PORT),
        HealthHandler
    )

    print(
        f"🌐 Health server running on port {PORT}"
    )

    server.serve_forever()


# ==========================================
# Automatic Price Collector
# ==========================================

def automatic_price_collector():

    print(
        "🤖 AUTO COLLECTOR STARTED"
    )

    print(
        f"⏱️ Collection interval: "
        f"{COLLECT_INTERVAL} seconds"
    )

    while True:

        try:

            # ==================================
            # Get Price
            # ==================================

            print(
                "📡 AUTO: Requesting price from TGJU..."
            )

            data = get_gold_18k()

            print(
                "📥 AUTO: Price received: "
                f"{data['price']:,} "
                f"{data['currency']}"
            )

            # ==================================
            # Save Raw Price
            # ==================================

            save_price(data)

            print(
                "💾 AUTO: Price saved successfully."
            )

            # ==================================
            # Build 1 Minute Candle
            # ==================================

            try:

                candle = build_1m_candle(
                    symbol=data["symbol"]
                )

                if candle:

                    print(
                        "🕯️ AUTO: 1M candle updated."
                    )

            except Exception as candle_error:

                print(
                    "❌ CANDLE ENGINE ERROR: "
                    f"{type(candle_error).__name__}: "
                    f"{candle_error}"
                )

        except Exception as error:

            print(
                "❌ AUTO COLLECTOR ERROR: "
                f"{type(error).__name__}: {error}"
            )

        print(
            f"⏳ AUTO: Waiting "
            f"{COLLECT_INTERVAL} seconds..."
        )

        time.sleep(COLLECT_INTERVAL)


# ==========================================
# Telegram /start
# ==========================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n\n"
        "📊 سیستم جمع‌آوری قیمت طلای ایران فعال است.\n\n"
        "👇 برای استفاده از ربات از دکمه‌های زیر استفاده کن.",
        reply_markup=get_main_keyboard()
    )


# ==========================================
# Telegram /help
# ==========================================

async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    await update.message.reply_text(
        "ℹ️ راهنمای Iran Gold AI\n\n"
        "🟡 قیمت لحظه‌ای\n"
        "دریافت آخرین قیمت طلای ۱۸ عیار از TGJU\n\n"
        "📊 تاریخچه\n"
        "نمایش آخرین قیمت‌های ذخیره‌شده\n\n"
        "🔄 بروزرسانی\n"
        "دریافت قیمت جدید و ذخیره آن در دیتابیس\n\n"
        "ℹ️ راهنما\n"
        "نمایش همین راهنما\n\n"
        "🔮 در مراحل بعد:\n"
        "تحلیل بازار، روند، مناطق خرید، "
        "اهداف قیمتی و امتیاز سیگنال اضافه خواهد شد.",
        reply_markup=get_main_keyboard()
    )


# ==========================================
# Telegram /price
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
            "💾 MANUAL: Price saved successfully."
        )

        # ساخت/به‌روزرسانی کندل
        try:

            candle = build_1m_candle(
                symbol=data["symbol"]
            )

            if candle:

                print(
                    "🕯️ MANUAL: 1M candle updated."
                )

        except Exception as candle_error:

            print(
                "❌ MANUAL CANDLE ERROR: "
                f"{type(candle_error).__name__}: "
                f"{candle_error}"
            )

        price = data["price"]

        await update.message.reply_text(
            "🟡 طلای ۱۸ عیار\n\n"
            f"💰 قیمت: {price:,} ریال\n"
            f"📡 منبع: {data['source']}",
            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            f"❌ MANUAL PRICE ERROR: "
            f"{type(error).__name__}: {error}"
        )

        await update.message.reply_text(
            "❌ خطای دریافت قیمت:\n\n"
            f"{type(error).__name__}: {error}",
            reply_markup=get_main_keyboard()
        )


# ==========================================
# Telegram /history
# ==========================================

async def history_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):

    try:

        rows = get_latest_prices(10)

        if not rows:

            await update.message.reply_text(
                "📭 هنوز هیچ قیمتی در دیتابیس ذخیره نشده است.",
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

            price, currency, source, timestamp = row

            message += (
                f"{index}. 💰 {price:,} {currency}\n"
                f"   📡 {source}\n"
                f"   🕐 {timestamp}\n\n"
            )

        await update.message.reply_text(
            message,
            reply_markup=get_main_keyboard()
        )

    except Exception as error:

        print(
            f"❌ HISTORY ERROR: "
            f"{type(error).__name__}: {error}"
        )

        await update.message.reply_text(
            "❌ خطا در خواندن تاریخچه:\n\n"
            f"{type(error).__name__}: {error}",
            reply_markup=get_main_keyboard()
        )


# ==========================================
# Button Menu Handler
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
    # Render Health Server
    # ======================================

    health_thread = threading.Thread(
        target=run_health_server,
        daemon=True
    )

    health_thread.start()

    # ======================================
    # Automatic Collector
    # ======================================

    collector_thread = threading.Thread(
        target=automatic_price_collector,
        daemon=True
    )

    collector_thread.start()

    # ======================================
    # Telegram Application
    # ======================================

    application = (
        Application
        .builder()
        .token(BOT_TOKEN)
        .build()
    )

    # ======================================
    # Command Handlers
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
    # Button Handler
    # ======================================

    application.add_handler(
        MessageHandler(
            filters.TEXT & ~filters.COMMAND,
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
