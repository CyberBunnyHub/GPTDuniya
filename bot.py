# bot.py

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
from config import *

import random

# Pyrogram Client
app = Client("AutoFilterBot", bot_token=BOT_TOKEN)

# MongoDB
mongo = MongoClient(MONGO_URI)
db = mongo[DB_NAME][COLLECTION_NAME]

# /start command
@app.on_message(filters.private & filters.command("start"))
async def start_cmd(client, message: Message):
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS)
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("Help", callback_data="help"),
         InlineKeyboardButton("About", callback_data="about")],
        [InlineKeyboardButton("Update Channel", url=UPDATE_CHANNEL)],
        [InlineKeyboardButton("Support Group", url=SUPPORT_GROUP)]
    ])
    
    await message.reply_photo(photo=image, caption=caption, reply_markup=keyboard)

# Button callbacks
@app.on_callback_query()
async def cb_handler(client, callback):
    data = callback.data
    if data == "help":
        await callback.message.edit_caption("Send a movie name and I will try to find matching files.")
    elif data == "about":
        await callback.message.edit_caption("Auto Filter Bot v1.0 | Built with Pyrogram and MongoDB.")
    await callback.answer()

# Store new files (only from DB Channel)
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & filters.document)
async def save_to_db(client, message: Message):
    if not message.caption:
        return
    db.insert_one({
        "file_id": message.document.file_id,
        "file_name": message.caption.lower()
    })

# Search handler (private + group)
@app.on_message(filters.text & ~filters.command(["start"]))
async def search_file(client, message: Message):
    query = message.text.strip().lower()
    results = list(db.find({"file_name": {"$regex": f"^{query}"}}))

    if not results:
        await message.reply("No results found.")
        return

    buttons = [
        [InlineKeyboardButton(doc["file_name"], callback_data=f"get_{doc['file_id']}")]
        for doc in results[:10]
    ]
    await message.reply("Results found:", reply_markup=InlineKeyboardMarkup(buttons))

# File callback
@app.on_callback_query(filters.regex(r"get_"))
async def send_file(client, callback):
    file_id = callback.data.split("_", 1)[1]
    await callback.message.reply_document(file_id)
    await callback.answer()

app.run()
