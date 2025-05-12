from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram import filters

WELCOME_IMAGE = "https://telegra.ph/file/9c6f8196ff3be9c3e902e.jpg"
WELCOME_CAPTION = (
    "**Welcome to AutoFilter Bot!**\n\n"
    "This bot helps you search files shared in your group automatically!"
)

WELCOME_BUTTONS = [
    [InlineKeyboardButton("How to Use", url="https://t.me/yourchannel")],
    [InlineKeyboardButton("Search Example", url="https://t.me/yourchannel")],
    [InlineKeyboardButton("Join Updates", url="https://t.me/yourupdates")],
    [InlineKeyboardButton("Add to Group", url="https://t.me/YourBot?startgroup=true")],
    [InlineKeyboardButton("Developer", url="https://t.me/yourusername")],
]

def register(app):
    @app.on_message(filters.command("start") & filters.private)
    async def start_command(client, message):
        await message.reply_photo(
            photo=WELCOME_IMAGE,
            caption=WELCOME_CAPTION,
            reply_markup=InlineKeyboardMarkup(WELCOME_BUTTONS)
        )
