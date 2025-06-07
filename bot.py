import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest
from dotenv import load_dotenv
import os

# Load config
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
REQUIRED_CHANNEL = os.getenv("REQUIRED_CHANNEL")

# Logging
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_subscription(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Check if user is subscribed to the channel"""
    try:
        member = await context.bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except BadRequest:
        return False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command - verify subscription"""
    user = update.effective_user
    if await check_subscription(user.id, context):
        await update.message.reply_text("✅ **Access granted!** You're subscribed.")
    else:
        await update.message.reply_text(
            "❌ **Please join our channel first:**",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Join Channel", url=f"https://t.me/{REQUIRED_CHANNEL[1:]}")]
            ])
        )

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.run_polling()

if __name__ == "__main__":
    main()
