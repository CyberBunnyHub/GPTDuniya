from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import ChatAdminRequired, UserNotParticipant
from pymongo import MongoClient
from bson import ObjectId
from pyrogram.enums import ParseMode
import random

from config import (
    BOT_TOKEN, API_ID, API_HASH, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, SUPPORT_GROUP
)

# Initialize bot
app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# MongoDB setup
mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

# Check subscription
async def check_subscription(client, user_id):
    try:
        member = await client.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except Exception:
        return True


# Generate pagination buttons
def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query=""):
    total_pages = (len(results) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_data = results[start:end]

    buttons = [
        [InlineKeyboardButton(
            f"🎬 {doc.get('file_name', 'Unnamed')[:30]}",
            url=f"https://t.me/{bot_username}?start={doc['_id']}"
        )] for doc in page_data
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
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS).format(message.from_user.id)

    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Update Channel", url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("✅ Joined", callback_data="checksub")]
        ])
        return await message.reply("🚫 To use this bot, please join our update channel first.", reply_markup=keyboard)

    args = message.text.split()
    if len(args) > 1:
        try:
            doc = files_col.find_one({"_id": ObjectId(args[1])})
            if not doc:
                return await message.reply("❌ File not found.")
            return await client.copy_message(chat_id=message.chat.id, from_chat_id=doc["chat_id"], message_id=doc["message_id"])
        except Exception as e:
            return await message.reply(f"❌ Error retrieving file:\n\n`{e}`")

    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aᴅᴅ Mᴇ Tᴏ Gʀᴏᴜᴘ", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("Hᴇʟᴘ", callback_data="help"), InlineKeyboardButton("Aʙᴏᴜᴛ", callback_data="about")],
        [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL), InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
    ])
    await message.reply_photo(image, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

# Bot added to group
@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message: Message):
    for member in message.new_chat_members:
        if member.id == (await client.get_me()).id:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL), InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
    ])
            await message.reply("TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇh Tᴏ Yᴏᴜʀ Gʀᴏᴜᴘ , Lᴇᴛs Sᴛᴀʀᴛ Tʜᴇ Gᴀᴍᴇ...😂", reply_markup=keyboard)


# Save files from DB_CHANNEL
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    if not message.caption:
        return
    file_name = message.caption.strip().lower()
    file_doc = {
        "file_name": file_name,
        "chat_id": message.chat.id,
        "message_id": message.id
    }
    result = files_col.insert_one(file_doc)
    print(f"Saved file with ID: {result.inserted_id}")


# Search handler
@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about", "delete"]) & ~filters.bot)
async def search_file(client, message: Message):
    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Update Channel", url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("✅ Joined", callback_data="checksub")]
        ])
        return await message.reply("🚫 To use this bot, please join our update channel first.", reply_markup=keyboard)

    query = message.text.strip().lower()
    
    # File search
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))
    if not results:
        return  # stay silent if no results

    markup = generate_pagination_buttons(results, (await client.get_me()).username, page=0, per_page=5, prefix="search", query=query)
    await message.reply("✅ Results found:", reply_markup=markup)

# Callback queries
@app.on_callback_query()
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data

    if data.startswith(("search:", "movie:")):
        prefix, page_str, query_text = data.split(":", 2)
        page = int(page_str)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}})) if prefix == "search" else list(files_col.find())
        markup = generate_pagination_buttons(results, (await client.get_me()).username, page, per_page=5, prefix=prefix, query=query_text)
        try:
            await query.message.edit_text("✅ Results found:" if prefix == "search" else "Choose a movie:", reply_markup=markup)
        except Exception:
            pass
        await query.answer()

    elif data == "help":
        help_text = (
           "Wᴇʟᴄᴏᴍᴇ! Tᴏ Mʏ Sᴛᴏʀᴇ"
        )
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton(("</Bᴀᴄᴋ>", callback_data="back")]])
        await query.message.edit_text(help_text, reply_markup=keyboard)
        await query.answer()

    elif data == "about":
        about_text = (
            """- - - - - - 🍿Aʙᴏᴜᴛ Mᴇh - - - - - - 

-ˋˏ✄- - Iᴍ Aɴ <a href='https://tg.me/{bot_username}'>Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</a> 
-ˋˏ✄- - Bᴜɪʟᴛ Wɪᴛʜ 💌 <a href='https://www.python.org/'>Pʏᴛʜᴏɴ</a> & <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ</a>
-ˋˏ✄- - DᴀᴛᴀBᴀsᴇ : <a href='https://www.mongodb.com/'>Mᴏɴɢᴏ Dʙ</a>
-ˋˏ✄- - Bᴏᴛ Sᴇʀᴠᴇʀ : <a href='https://Render.com/'>Rᴇɴᴅᴇʀ</a>"""
)
        keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data="back")]])
        await query.message.edit_text(about_text, reply_markup=keyboard)
        await query.answer()

    elif data == "back":
        image = random.choice(IMAGE_URLS)
        caption = random.choice(CAPTIONS)
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Aᴅᴅ Mᴇ Tᴏ Gʀᴏᴜᴘ", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
            [InlineKeyboardButton("Hᴇʟᴘ", callback_data="help"), InlineKeyboardButton("Aʙᴏᴜᴛ", callback_data="about")],
            [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL), InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
        ])
        try:
            await query.message.delete()
            await query.message.reply_photo(image, caption=caption, reply_markup=keyboard)
        except Exception:
            await query.message.edit_caption(caption, reply_markup=keyboard)
        await query.answer()

    elif data == "checksub":
        if await check_subscription(client, query.from_user.id):
            await query.message.edit_text("✅ You're subscribed! You can now use the bot.")
        else:
            await query.answer("❌ You're still not subscribed.", show_alert=True)

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


# Track users
@app.on_message(filters.private & filters.text)
async def track_user(client, message: Message):
    users_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"name": message.from_user.first_name}},
        upsert=True
    )


# Track groups
@app.on_message(filters.group & filters.text)
async def track_group(client, message: Message):
    groups_col.update_one(
        {"_id": message.chat.id},
        {"$set": {"title": message.chat.title}},
        upsert=True
    )


print("Bot is starting...")
app.run()
