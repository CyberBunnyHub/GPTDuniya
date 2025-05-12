from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

app = Client("autofilter_bot")

@app.on_message(filters.command("start"))
async def start(_, message: Message):
    await message.reply_photo(
        photo="https://placehold.co/600x400",
        caption="I can help you auto filter files in groups! Just add me and send a message.",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("Add Me To Group", url="https://t.me/YourBot?startgroup=true")],
             [InlineKeyboardButton("About", callback_data="about"),
              InlineKeyboardButton("Help", callback_data="help")]]
        )
    )

app.run()
