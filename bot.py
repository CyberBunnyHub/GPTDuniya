#!/usr/bin/env python3
import logging
import random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# List of image URLs (currently one URL; add more if desired)
IMAGE_URLS = [
    "https://example.com/your_image.jpg"  # Replace with your actual image URL
]

# List of sample captions
CAPTIONS = [
    "Hello there! Welcome to AutoFilter Bot.",
    "Hi! I'm your AutoFilter Bot, ready to serve!",
    "Greetings! Let me filter for you."
]

# URLs for the buttons (replace these later with your actual channel/group links)
UPDATE_CHANNEL_URL = "https://t.me/YourUpdateChannel"
SUPPORT_GROUP_URL = "https://t.me/YourSupportGroup"

def start(update: Update, context: CallbackContext) -> None:
    """Sends a random image with a random caption and an inline keyboard."""
    # Choose a random image and caption
    selected_image = random.choice(IMAGE_URLS)
    selected_caption = random.choice(CAPTIONS)
    
    # Create inline keyboard with 5 buttons
    keyboard = [
        # Button for adding the bot to a group
        [InlineKeyboardButton("Add Me to Group", url=f"https://t.me/{context.bot.username}?startgroup=true")],
        # Buttons for Help and About as callbacks
        [InlineKeyboardButton("Help", callback_data="help"),
         InlineKeyboardButton("About", callback_data="about")],
        # Buttons for Update Channel and Support Group
        [InlineKeyboardButton("Update Channel", url=UPDATE_CHANNEL_URL)],
        [InlineKeyboardButton("Support Group", url=SUPPORT_GROUP_URL)]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Send the photo with the selected caption and inline keyboard
    update.message.reply_photo(photo=selected_image, caption=selected_caption, reply_markup=reply_markup)

def button_handler(update: Update, context: CallbackContext) -> None:
    """Handles callback queries from inline buttons."""
    query = update.callback_query
    query.answer()  # Acknowledge the callback query

    if query.data == "help":
        # Respond with help information – customize as needed
        query.edit_message_caption(caption="This is the help section. Use /start to restart the bot or explore more features soon!")
    elif query.data == "about":
        # Respond with about information – customize as needed
        query.edit_message_caption(caption="AutoFilter Bot v1.0\nCreated with love using Python and python-telegram-bot.")

def main() -> None:
    """Starts the bot."""
    # Replace 'YOUR_BOT_TOKEN_HERE' with your bot's token from BotFather
    BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"

    updater = Updater(BOT_TOKEN, use_context=True)
    dispatcher = updater.dispatcher

    # Add command and callback query handlers
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button_handler))

    # Start the Bot
    updater.start_polling()
    logger.info("Bot started. Press Ctrl+C to stop.")
    updater.idle()

if __name__ == '__main__':
    main()
