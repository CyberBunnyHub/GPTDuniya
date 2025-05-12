from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from pymongo import MongoClient
import random, base64
from config import BOT_TOKEN, API_ID, API_HASH, MONGO_URI, DB_CHANNEL, IMAGE_URLS, CAPTIONS, UPDATE_CHANNEL, SUPPORT_GROUP

app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB Setup
mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

# /start command
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    args = message.command

    if len(args) > 1 and args[1].startswith("file_"):
        try:
            file_id = base64.urlsafe_b64decode(args[1][5:]).decode()
            await message.reply_document(file_id)
            return
        except Exception as e:
            await message.reply(f"❌ Failed to send file:\n`{e}`")
            return

    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS)

    buttons = [
        [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help"), InlineKeyboardButton("📌 About", callback_data="about")],
        [InlineKeyboardButton("📢 Updates", url=UPDATE_CHANNEL)],
        [InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)]
    ]

    await message.reply_photo(image, caption=caption, reply_markup=InlineKeyboardMarkup(buttons))

# Save files from DB_CHANNEL
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & filters.document)
async def save_file(client, message: Message):
    if not message.caption:
        return
    data = {
        "file_id": message.document.file_id,
        "file_name": message.caption.lower()
    }
    files_col.insert_one(data)

# Search handler
@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about"]) & ~filters.bot)
async def search_file(client, message: Message):
    query = message.text.strip().lower()
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))

    if not results:
        await message.reply("No results found.")
        return

    buttons = []
    for doc in results[:10]:
        try:
            file_id = doc["file_id"]
            encoded = base64.urlsafe_b64encode(file_id.encode()).decode()
            url = f"https://t.me/{(await client.get_me()).username}?start=file_{encoded}"
            buttons.append([InlineKeyboardButton(doc["file_name"].title()[:30], url=url)])
        except:
            continue

    await message.reply("Results found:", reply_markup=InlineKeyboardMarkup(buttons))

# /stats command
@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    total_users = users_col.count_documents({})
    total_groups = groups_col.count_documents({})
    total_files = files_col.count_documents({})

    text = (
        "**Bot Stats:**\n\n"
        f"**Users:** {total_users}\n"
        f"**Groups:** {total_groups}\n"
        f"**Total Files:** {total_files}\n\n"
    )

    await message.reply(text)

# Track users
@app.on_message(filters.private & filters.text)
async def track_user(client, message: Message):
    user_id = message.from_user.id
    users_col.update_one({"_id": user_id}, {"$set": {"name": message.from_user.first_name}}, upsert=True)

# Track groups
@app.on_message(filters.group & filters.text)
async def track_group(client, message: Message):
    group_id = message.chat.id
    groups_col.update_one({"_id": group_id}, {"$set": {"title": message.chat.title}}, upsert=True)

print("Bot is starting...")
app.run()
