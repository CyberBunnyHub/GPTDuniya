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
    args = message.text.split()

    if len(args) > 1 and args[1].startswith("file_"):
        try:
            encoded_data = args[1][5:]
            decoded = base64.urlsafe_b64decode(encoded_data).decode()
            chat_id_str, msg_id_str = decoded.split("_")
            chat_id = int(chat_id_str)
            msg_id = int(msg_id_str)

            await client.copy_message(chat_id=message.chat.id, from_chat_id=chat_id, message_id=msg_id)
            return
        except Exception as e:
            await message.reply(f"❌ Error while sending the file.\n\n`{e}`")
            return

    # Normal start message
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Me to Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("Help", callback_data="help"), InlineKeyboardButton("About", callback_data="about")],
        [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL)],
        [InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
    ])

    await message.reply_photo(image, caption=caption, reply_markup=keyboard)

# Save files from DB_CHANNEL
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & filters.document)
async def save_file(client, message: Message):
    if not message.caption:
        return

    files_col.insert_one({
        "file_name": message.caption.lower(),
        "chat_id": message.chat.id,
        "message_id": message.id
    })

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
            chat_id = doc.get("chat_id")
            msg_id = doc.get("message_id")
            file_name = doc.get("file_name", "File")

            if not chat_id or not msg_id:
                continue  # Skip if essential fields are missing

            encoded = base64.urlsafe_b64encode(f"{chat_id}_{msg_id}".encode()).decode()
            url = f"https://t.me/{(await client.get_me()).username}?start=file_{encoded}"

            # Fallback if filename is missing
            if not isinstance(file_name, str) or not file_name.strip():
                file_name = "Unnamed File"

            buttons.append([InlineKeyboardButton(file_name[:30], url=url)])
        except Exception as e:
            print(f"Error generating button: {e}")
            continue

    if not buttons:
        await message.reply("No valid files found.")
        return

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
        f"**Total Files:** {total_files}"
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
