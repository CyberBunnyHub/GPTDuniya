from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import ChatAdminRequired
from pymongo import MongoClient
from bson import ObjectId
import random

# Import configuration
from config import (
    BOT_TOKEN, API_ID, API_HASH, MONGO_URI, DB_CHANNEL,
    IMAGE_URLS, CAPTIONS, UPDATE_CHANNEL, SUPPORT_GROUP
)

# Initialize bot
app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB setup
mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

# Generate pagination buttons
def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query=""):
    total_pages = (len(results) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_data = results[start:end]

    buttons = [
        [InlineKeyboardButton(f"🎬 {doc.get('file_name', 'Unnamed')[:30]}", url=f"https://t.me/{bot_username}?start={doc['_id']}")]
        for doc in page_data
    ]

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}:{page - 1}:{query}"))
    nav_buttons.append(InlineKeyboardButton(f"Page {page + 1}/{total_pages}", callback_data="noop"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}:{page + 1}:{query}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)

# /start command
@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    args = message.text.split()
    if len(args) > 1:
        try:
            doc = files_col.find_one({"_id": ObjectId(args[1])})
            if not doc:
                return await message.reply("❌ File not found.")
            await client.copy_message(chat_id=message.chat.id, from_chat_id=doc["chat_id"], message_id=doc["message_id"])
        except Exception as e:
            await message.reply(f"❌ Error retrieving file:\n\n`{e}`")
        return

    # Default start screen
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS)
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("Help", callback_data="help"), InlineKeyboardButton("About", callback_data="about")],
        [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL)],
        [InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
    ])
    await message.reply_photo(image, caption=caption, reply_markup=keyboard)

# Save incoming files from DB_CHANNEL
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    if not message.caption:
        return

    file_name = message.caption.strip().lower()
    file_doc = {
        "file_name": file_name,
        "chat_id": message.chat.id,
        "message_id": message.id  # <-- Corrected this line
    }
    result = files_col.insert_one(file_doc)
    print(f"Saved file with ID: {result.inserted_id}")

# Text-based search
@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about", "movie", "delete"]) & ~filters.bot)
async def search_file(client, message: Message):
    query = message.text.strip().lower()
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))

    if not results:
        return await message.reply("❌ No results found.")

    markup = generate_pagination_buttons(results, (await client.get_me()).username, page=0, per_page=5, prefix="search", query=query)
    await message.reply("✅ Results found:", reply_markup=markup)

# /movie command (list all files)
@app.on_message(filters.command("movie") & filters.group)
async def send_movie_list(client, message: Message):
    results = list(files_col.find())
    if not results:
        return await message.reply("❌ No movies found.")

    markup = generate_pagination_buttons(results, (await client.get_me()).username, page=0, per_page=5, prefix="movie")
    await message.reply("Choose a movie:", reply_markup=markup)

# Handle pagination callbacks
@app.on_callback_query()
async def pagination_handler(client, query: CallbackQuery):
    data = query.data
    if data.startswith(("search:", "movie:")):
        prefix, page_str, query_text = data.split(":", 2)
        page = int(page_str)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}})) if prefix == "search" else list(files_col.find())
        markup = generate_pagination_buttons(results, (await client.get_me()).username, page, per_page=5, prefix=prefix, query=query_text)
        try:
            await query.message.edit_text("✅ Results found:" if prefix == "search" else "Choose a movie:", reply_markup=markup)
        except Exception:
            pass  # Avoid MESSAGE_NOT_MODIFIED
        await query.answer()
    elif data == "noop":
        await query.answer()

# /stats command
@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    users = users_col.count_documents({})
    groups = groups_col.count_documents({})
    files = files_col.count_documents({})
    text = f"**Bot Stats:**\n\n**Users:** {users}\n**Groups:** {groups}\n**Total Files:** {files}"
    await message.reply(text)

# Track new users
@app.on_message(filters.private & filters.text)
async def track_user(client, message: Message):
    users_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"name": message.from_user.first_name}},
        upsert=True
    )

# Track new groups
@app.on_message(filters.group & filters.text)
async def track_group(client, message: Message):
    groups_col.update_one(
        {"_id": message.chat.id},
        {"$set": {"title": message.chat.title}},
        upsert=True
    )

# /delete command (admin only)
@app.on_message(filters.command("delete") & filters.group)
async def delete_file(client, message: Message):
    member = await client.get_chat_member(message.chat.id, message.from_user.id)
    if member.status not in ("administrator", "creator"):
        return await message.reply("❌ Only admins can delete files.")

    if len(message.command) < 2:
        return await message.reply("Usage: /delete <file name>")

    file_name = " ".join(message.command[1:]).strip().lower()
    result = files_col.find_one_and_delete({"file_name": {"$regex": f"^{file_name}$", "$options": "i"}})

    if result:
        await message.reply(f"✅ Deleted file: `{result.get('file_name', 'Unknown')}`")
    else:
        await message.reply("❌ File not found.")

print("Bot is starting...")
app.run()
