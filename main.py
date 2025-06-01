from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackContext, CommandHandler
import time

def start(update: Update, context: CallbackContext):
    # 1. Send popcorn emoji 🍿
    sent_message = context.bot.send_message(
        chat_id=update.effective_chat.id,
        text="🍿"
    )

    # 2. Wait, then delete the emoji message
    time.sleep(1)
    context.bot.delete_message(
        chat_id=update.effective_chat.id,
        message_id=sent_message.message_id
    )

    # 3. Send image with caption and 5 inline buttons
    image_url = "https://emoji.slack-edge.com/T024FPYBQ/popcorn/2f8c6c6c7f5a8b7b.png"
    caption = "🍿 Loading... Please choose an option:"

    keyboard = [
        [InlineKeyboardButton("Button 1", callback_data='btn1')],
        [InlineKeyboardButton("Button 2", callback_data='btn2')],
        [InlineKeyboardButton("Button 3", callback_data='btn3')],
        [InlineKeyboardButton("Button 4", callback_data='btn4')],
        [InlineKeyboardButton("Button 5", callback_data='btn5')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    context.bot.send_photo(
        chat_id=update.effective_chat.id,
        photo=image_url,
        caption=caption,
        reply_markup=reply_markup
    )

# Remember to register this handler with:
# dispatcher.add_handler(CommandHandler("start", start))
