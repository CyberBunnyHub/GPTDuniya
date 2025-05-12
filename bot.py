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
    args = message.command

    # Check if a file_id is passed in /start
    if len(args) > 1:
        file_id = args[1]
        try:
            await message.reply_document(file_id)
        except Exception as e:
            await message.reply(f"Error sending file: {e}")
        return

    # Default start response with image and buttons
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

from bson.objectid import ObjectId

@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & filters.document)
async def save_to_db(client, message: Message):
    if not message.caption:
        return
    data = {
        "file_id": message.document.file_id,
        "file_name": message.caption.lower()
    }
    db.insert_one(data)

@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about"]) & ~filters.me)
async def search_file(client, message: Message):
    query = message.text.strip().lower()
    results = list(db.find({"file_name": {"$regex": query, "$options": "i"}}))

    if not results:
        await message.reply("No results found.")
        return

    buttons = [
        [InlineKeyboardButton(
            doc["file_name"].title(),
            url=f"https://t.me/{(await client.get_me()).username}?start={doc['file_id']}"
        )]
        for doc in results[:10]
    ]

    await message.reply("Results found:", reply_markup=InlineKeyboardMarkup(buttons))

from bson import ObjectId

@app.on_callback_query(filters.regex(r"get_(.*)"))
async def send_file(client, callback_query):
    mongo_id = callback_query.data.split("_", 1)[1]
    try:
        doc = db.find_one({"_id": ObjectId(mongo_id)})
        if not doc:
            await callback_query.message.reply("File not found.")
            return
        await callback_query.message.reply_document(doc["file_id"])
        await callback_query.answer("File sent.")
    except Exception as e:
        await callback_query.message.reply(f"Error: {e}")
        await callback_query.answer("Failed.", show_alert=True)

@app.on_message(filters.command("dump") & filters.user(6887303054))
async def dump(client, message):
    files = list(db.find())
    if not files:
        await message.reply("DB is empty.")
    else:
        reply_text = "\n".join([f"{x['file_name']}" for x in files[:5]])
        await message.reply(f"Sample stored files:\n{reply_text}")

users_col = mongo["autofilter"]["users"]
groups_col = mongo["autofilter"]["groups"]

@app.on_message(filters.private & filters.text)
async def track_user(client, message: Message):
    user_id = message.from_user.id
    users_col.update_one({"_id": user_id}, {"$set": {"name": message.from_user.first_name}}, upsert=True)


@app.on_message(filters.group & filters.text)
async def track_group(client, message: Message):
    chat_id = message.chat.id
    groups_col.update_one({"_id": chat_id}, {"$set": {"title": message.chat.title}}, upsert=True)
    
@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    total_users = users_col.count_documents({})
    total_groups = groups_col.count_documents({})
    total_files = db.count_documents({})
    samples = db.find().limit(5)

    sample_names = "\n".join([f"• {x['file_name']}" for x in samples])
    sample_text = sample_names if sample_names else "No files yet."

    text = (
        "**Bot Stats:**\n\n"
        f"**Users:** {total_users}\n"
        f"**Groups:** {total_groups}\n"
        f"**Total files:** {total_files}\n\n"
        f"**Sample files:**\n{sample_text}"
    )

    await message.reply(text)

print("Bot is starting...")
app.run()
