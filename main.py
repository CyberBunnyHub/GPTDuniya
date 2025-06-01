import asyncio
from pyrogram import Client, filters, enums
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
)
import pymongo

# ========== CONFIG ==========
LOG_CHANNEL = -1002615219160
BOT_TOKEN = "7845318227:AAFIWjneKzVu_MmAsNDkD3B6NvXzlbMdCgU"
DB_CHANNEL = -1002511163521
API_ID = "14853951"
API_HASH = "0a33bc287078d4dace12aaecc8e73545"
BOT_OWNER = 6887303054
MONGO_URI = "mongodb+srv://CyberBunny:Bunny2008@cyberbunny.5yyorwj.mongodb.net/?retryWrites=true&w=majority"
DB_NAME = "CyberBunny"
COLLECTION_NAME = "CBI"
IMAGE_URLS = [
    "https://ibb.co/zVGqb88W"
]
CAPTIONS = [
    """<blockquote>Hᴇʟʟᴏ {user_mention} 👋,</blockquote>\n
I'ᴍ Lᴀᴛᴇꜱᴛ Aᴅᴠᴀɴᴄᴇᴅ & Pᴏᴡᴇʀꜰᴜʟ Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ. Yᴏᴜ Cᴀɴ Uꜱᴇ Mᴇ Tᴏ Gᴇᴛ Mᴏᴠɪᴇs🍿 [Jᴜsᴛ Sᴇɴᴅ Mᴇ Mᴏᴠɪᴇ Nᴀᴍᴇ] Oʀ Yᴏᴜ Cᴀɴ Aᴅᴅ Mᴇ Tᴏ Yᴏᴜʀ Gʀᴏᴜᴘ & Mᴀɢɪᴄ Hᴀᴘᴘᴇɴs!."""
]
UPDATE_CHANNEL = "https://t.me/+giwNAm14E38xYjI9"
SUPPORT_GROUP = "https://t.me/VirabGroup"

# ========== DATABASE ==========
mongo_client = pymongo.MongoClient(MONGO_URI)
db = mongo_client[DB_NAME]
collection = db[COLLECTION_NAME]

def add_file_if_not_exists(file_dict):
    """Insert a file only if it does not already exist (by file_id)."""
    exists = collection.find_one({"file_id": file_dict["file_id"]})
    if exists:
        return False
    collection.insert_one(file_dict)
    return True

def search_by_movie(movie_name):
    return list(collection.find({"movie_name": {"$regex": movie_name, "$options": "i"}}))

def get_languages_for_movie(movie_name):
    langs = collection.distinct("language", {"movie_name": {"$regex": movie_name, "$options": "i"}})
    return [l for l in langs if l]

def get_files_by_movie_and_lang(movie_name, lang):
    return list(collection.find({"movie_name": {"$regex": movie_name, "$options": "i"}, "language": lang}))

async def get_stats():
    files = collection.count_documents({})
    chats = len(collection.distinct("chat_id"))
    users = len(collection.distinct("user_id"))
    return {"files": files, "chats": chats, "users": users}

# ========== BOT INIT ==========
app = Client(
    "autofilterbot",
    bot_token=BOT_TOKEN,
    api_id=API_ID,
    api_hash=API_HASH
)

START_EMOJI = "✨"
WELCOME_TEXT = "Welcome! Please choose an option below:"
ABOUT_TEXT = (
    "🤖 <b>Bot Name:</b> Auto Filter Bot\n"
    "👨‍💻 <b>Developer:</b> <a href='tg://user?id={}'>{}</a>\n"
    "📢 <b>Updates:</b> <a href='{}'>Channel</a>\n"
    "💬 <b>Support:</b> <a href='{}'>Group</a>"
).format(BOT_OWNER, "Owner", UPDATE_CHANNEL, SUPPORT_GROUP)
ADMIN_CMDS = (
    "<b>Admin Commands:</b>\n"
    "/broadcast\n"
    "/grp_broadcast\n"
    "/users\n"
    "/chats\n"
    "<i>(these can be implemented to your needs)</i>"
)

def main_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Me to Group", url="https://t.me/CyberBunnyAutoBot?startgroup=true")],
        [InlineKeyboardButton("❓ Help", callback_data="help"),
         InlineKeyboardButton("ℹ️ About", callback_data="about")],
        [InlineKeyboardButton("📢 Updates", url=UPDATE_CHANNEL),
         InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)]
    ])

def help_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Stats", callback_data="stats"),
         InlineKeyboardButton("🗄 Database", callback_data="database"),
         InlineKeyboardButton("👮 Admins", callback_data="admins")],
        [InlineKeyboardButton("🔙 Back", callback_data="back")]
    ])

def admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💌 Broadcast", callback_data="cb_broadcast"),
         InlineKeyboardButton("📢 Group Broadcast", callback_data="cb_grp_broadcast")],
        [InlineKeyboardButton("👤 Users", callback_data="cb_users"),
         InlineKeyboardButton("👥 Chats", callback_data="cb_chats")],
        [InlineKeyboardButton("✨ Give Features", callback_data="cb_givefeatures")],
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ])

def features_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🔙 Back", callback_data="admins")]
    ])

# ========== CALLBACK HANDLERS ==========

@app.on_callback_query()
async def callback_query_handler(client: Client, query: CallbackQuery):
    data = query.data

    if data == "help":
        await query.message.edit_text(
            WELCOME_TEXT,
            reply_markup=help_keyboard()
        )

    elif data == "about":
        await query.message.edit_text(
            ABOUT_TEXT,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ]),
            parse_mode="HTML",
            disable_web_page_preview=True
        )

    elif data == "stats":
        stats = await get_stats()
        stats_txt = (
            f"<b>Stats:</b>\n"
            f"Files: <code>{stats['files']}</code>\n"
            f"Chats: <code>{stats['chats']}</code>\n"
            f"Users: <code>{stats['users']}</code>"
        )
        await query.message.edit_text(
            stats_txt,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ]),
            parse_mode="HTML"
        )

    elif data == "database":
        await query.message.edit_text(
            "Please wait...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
        )

    elif data == "admins":
        await query.message.edit_text(
            "<b>Admin Panel</b>\nChoose an action:",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cb_broadcast":
        await query.message.edit_text(
            "To broadcast a message to all users, use /broadcast <message> in private chat.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cb_grp_broadcast":
        await query.message.edit_text(
            "To broadcast a message to all groups, use /grp_broadcast <message> in private chat.",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cb_users":
        stats = await get_stats()
        await query.message.edit_text(
            f"Total Users: <b>{stats['users']}</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cb_chats":
        stats = await get_stats()
        await query.message.edit_text(
            f"Total Chats: <b>{stats['chats']}</b>",
            reply_markup=admin_keyboard(),
            parse_mode="HTML"
        )

    elif data == "cb_givefeatures":
        await query.message.edit_text(
            "<b>Features:</b>\n"
            "• Auto movie filter/search\n"
            "• Language filtering\n"
            "• Send all files at once\n"
            "• Inline admin panel\n"
            "• Stats and database info\n"
            "• Group and user broadcast\n"
            "• And more!",
            reply_markup=features_keyboard(),
            parse_mode="HTML"
        )

    elif data == "back":
        await query.message.edit_caption(
            CAPTIONS[0].format(user_mention=query.from_user.mention),
            reply_markup=main_keyboard(),
            parse_mode="HTML"
        )

    elif data.startswith("filterlang_"):
        movie_name = data.split("_", 1)[1]
        langs = get_languages_for_movie(movie_name)
        lang_buttons = [
            [InlineKeyboardButton(lang, callback_data=f"lang_{movie_name}_{lang}")]
            for lang in langs
        ]
        lang_buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"backres_{movie_name}")])
        await query.message.edit_text(
            "Choose language:", reply_markup=InlineKeyboardMarkup(lang_buttons)
        )

    elif data.startswith("lang_"):
        _, movie_name, lang = data.split("_", 2)
        files = get_files_by_movie_and_lang(movie_name, lang)
        file_buttons = [
            [InlineKeyboardButton(file['file_name'], callback_data=f"file_{file['_id']}")]
            for file in files
        ]
        file_buttons.append([InlineKeyboardButton("🔙 Back", callback_data=f"filterlang_{movie_name}")])
        await query.message.edit_text(
            f"Files for <b>{movie_name}</b> [{lang}]:",
            reply_markup=InlineKeyboardMarkup(file_buttons),
            parse_mode="HTML"
        )

    elif data.startswith("allfiles_"):
        movie_name = data.split("_", 1)[1]
        files = search_by_movie(movie_name)
        if not files:
            await query.answer("No files found!", show_alert=True)
            return
        await query.message.edit_text(f"Sending all files for <b>{movie_name}</b>...", parse_mode="html")
        for file in files:
            try:
                await client.send_document(
                    chat_id=query.message.chat.id,
                    document=file['file_id'],
                    caption=file.get('file_name', None)
                )
            except Exception:
                continue

    elif data.startswith("file_"):
        file_id = data.split("_", 1)[1]
        file_doc = collection.find_one({"_id": pymongo.ObjectId(file_id)})
        if file_doc:
            try:
                await client.send_document(
                    chat_id=query.message.chat.id,
                    document=file_doc['file_id'],
                    caption=file_doc.get('file_name', None)
                )
            except Exception:
                await query.answer("Failed to send file.", show_alert=True)
        else:
            await query.answer("File not found!", show_alert=True)

# ========== START HANDLER ==========
@app.on_message(filters.command("start") & filters.private)
async def start_handler(client: Client, message: Message):
    emoji_msg = await message.reply(START_EMOJI)
    await asyncio.sleep(2)
    await emoji_msg.delete()
    await message.reply_photo(
        IMAGE_URLS[0],
        caption=CAPTIONS[0].format(user_mention=message.from_user.mention),
        reply_markup=main_keyboard(),
        parse_mode="HTML"
    )

# ========== GROUP HANDLER ==========
@app.on_message(
    filters.group & filters.text & ~filters.command(["start", "help"]) & ~filters.user("self")
)
async def group_movie_search_handler(client: Client, message: Message):
    if message.from_user is not None and message.from_user.is_bot:
        return
    query = message.text.strip()
    results = search_by_movie(query)
    if not results:
        return
    langs = get_languages_for_movie(query)
    buttons = []
    for file in results[:10]:
        buttons.append([InlineKeyboardButton(
            file['file_name'], callback_data=f"file_{file['_id']}")
        ])
    if langs:
        buttons.append([InlineKeyboardButton("🌐 Filter Language", callback_data=f"filterlang_{query}")])
    buttons.append([InlineKeyboardButton("📂 All Files", callback_data=f"allfiles_{query}")])
    await message.reply(
        f"Results for <b>{query}</b>:",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode="HTML"
    )

# ========== SAVE FILE TO DB_CHANNEL & INDEX ==========
@app.on_message(filters.document | filters.video | filters.audio)
async def save_file_and_index(client, message: Message):
    if message.chat.type == enums.ChatType.PRIVATE or message.chat.type == enums.ChatType.GROUP or message.chat.type == enums.ChatType.SUPERGROUP:
        # Forward/copy to DB_CHANNEL
        sent = await message.copy(DB_CHANNEL)
        # Get file_id and file_name
        if sent.document:
            file_id = sent.document.file_id
            file_name = sent.document.file_name
            file_size = sent.document.file_size
        elif sent.video:
            file_id = sent.video.file_id
            file_name = sent.video.file_name
            file_size = sent.video.file_size
        elif sent.audio:
            file_id = sent.audio.file_id
            file_name = sent.audio.file_name
            file_size = sent.audio.file_size
        else:
            return
        # Extract movie name (simple method: filename without extension)
        movie_name = file_name.rsplit('.', 1)[0] if file_name else "Unknown"
        # Try language from caption (very basic, improve if you wish)
        language = None
        if message.caption:
            for tag in ["[EN]", "[ENGLISH]", "[HINDI]", "[TELUGU]", "[MALAYALAM]"]:
                if tag.lower() in message.caption.lower():
                    language = tag.strip("[]").capitalize()
        # Prepare file data
        file_data = {
            "file_id": file_id,
            "file_name": file_name,
            "file_size": file_size,
            "movie_name": movie_name,
            "language": language,
            "message_id": sent.message_id,
            "channel_id": DB_CHANNEL,
            "chat_id": message.chat.id,
            "user_id": message.from_user.id if message.from_user else None
        }
        success = add_file_if_not_exists(file_data)
        if success:
            await message.reply("File saved and indexed!")
        else:
            await message.reply("This file is already indexed.")

# ========== RUN BOT ==========
if __name__ == "__main__":
    app.run()
