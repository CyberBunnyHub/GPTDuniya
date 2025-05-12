from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

@Client.on_message(filters.command("start"))
async def start(client, message: Message):
    buttons = InlineKeyboardMarkup(
        [[
            InlineKeyboardButton("About", callback_data="about"),
            InlineKeyboardButton("Help", callback_data="help")
        ]]
    )
    await message.reply_photo(
        photo="https://placehold.co/600x400",
        caption="Welcome to Auto Filter Bot!",
        reply_markup=buttons
    )
