import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)


load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🟡 سلام!\n\n"
        "من Iran Gold AI هستم.\n"
        "به‌زودی تحلیل بازار طلای ایران را برایت انجام می‌دهم."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 دستورات فعلی:\n\n"
        "/start - شروع ربات\n"
        "/help - راهنما"
    )


def main():
    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN is not configured."
        )

    application = Application.builder().token(BOT_TOKEN).build()

    application.add_handler(
        CommandHandler("start", start)
    )

    application.add_handler(
        CommandHandler("help", help_command)
    )

    print("🤖 Iran Gold AI Bot is running...")

    application.run_polling()


if __name__ == "__main__":
    main()
