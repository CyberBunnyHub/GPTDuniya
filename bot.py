from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import random
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URI, DB_CHANNEL, IMAGE_URLS, CAPTIONS, UPDATE_CHANNEL, SUPPORT_GROUP

app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]["files"]


@app.on_message(filters.command("start") & filters.private)
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

    await message.reply_photo(image, caption=caption, reply_markup=keyboard)


@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & filters.document)
async def save_to_db(client, message: Message):
    if not message.caption:
        return
    db.insert_one({
        "file_id": message.document.file_id,
        "file_name": message.caption.lower()
    })


@app.on_message(filters.text & ~filters.command(["start"]) & ~filters.me)
async def search_file(client, message: Message):
    query = message.text.strip().lower()
    results = list(db.find({"file_name": {"$regex": query, "$options": "i"}}))

    if not results:
        await message.reply("No results found.")
        return

    buttons = [
        [InlineKeyboardButton(doc["file_name"].title(), callback_data=f"get_{doc['file_id']}")]
        for doc in results[:10]
    ]
    await message.reply("Results found:", reply_markup=InlineKeyboardMarkup(buttons))


@app.on_callback_query(filters.regex(r"get_(.*)"))
async def send_file(client, callback_query):
    file_id = callback_query.data.split("_", 1)[1]
    await callback_query.message.reply_document(file_id)
    await callback_query.answer()

print("Bot is starting...")
app.run()
