import asyncio
import random
from bson import ObjectId
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)
from pyrogram.errors import UserNotParticipant

from config import (
    BOT_TOKEN, API_ID, API_HASH, BOT_OWNER, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, SUPPORT_GROUP
)

app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

def to_smallcaps_title(text):
    # Map normal letters to small caps letters (only A-Z and a-z)
    smallcaps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
    }

    def smallcap_char(c):
        lower = c.lower()
        return smallcaps_map.get(lower, c)

    def process_word(word):
        if not word:
            return word
        first = word[0].upper()
        rest = ''.join(smallcap_char(c) for c in word[1:].lower())
        return first + rest

    words = text.split()
    return ' '.join(process_word(word) for word in words)
    
async def check_subscription(client, user_id):
    try:
        member = await client.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except UserNotParticipant:
        return False
    except:
        return True

def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query="", user_id=None):
    total_pages = (len(results) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_data = results[start:end]

    buttons = []
    for doc in page_data:
        row = [InlineKeyboardButton(
            f"🎬 {doc.get('file_name', 'Unnamed')[:30]}",
            url=f"https://t.me/{bot_username}?start={doc['_id']}"
        )]
        if user_id == BOT_OWNER:
            row.append(InlineKeyboardButton("✘", callback_data=f"deletefile:{doc['_id']}"))
        buttons.append(row)

    if results:
        buttons.append([
            InlineKeyboardButton("Gᴇᴛ Aʟʟ Fɪʟᴇs", callback_data=f"getfiles:{query}"),
            InlineKeyboardButton("Lᴀɴɢᴜᴀɢᴇs", callback_data=f"langs:{query}:dummy")
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data=f"{prefix}:{page - 1}:{query}"))
    nav_buttons.append(InlineKeyboardButton(f"Page {page + 1}/{total_pages}", callback_data="noop"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton("</Nᴇxᴛ>", callback_data=f"{prefix}:{page + 1}:{query}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    emoji_msg = await message.reply("🍿")  # Loading animation
    image = random.choice(IMAGE_URLS)
    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    caption = random.choice(CAPTIONS).format(user_mention=user_mention)

    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Jᴏɪɴ Nᴏᴡ!", url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("Jᴏɪɴᴇᴅ", callback_data="checksub")]
        ])
        await emoji_msg.delete()
        return await message.reply("Tᴏ Usᴇ Tʜɪs Bᴏᴛ, Pʟᴇᴀsᴇ Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ Fɪʀsᴛ.", reply_markup=keyboard)

    args = message.text.split()
    if len(args) > 1:
        try:
            doc = files_col.find_one({"_id": ObjectId(args[1])})
            await emoji_msg.delete()
            if not doc:
                return await message.reply("❌ File not found.")
            return await client.copy_message(chat_id=message.chat.id, from_chat_id=doc["chat_id"], message_id=doc["message_id"])
        except Exception as e:
            await emoji_msg.delete()
            return await message.reply(f"❌ Error retrieving file:\n\n`{e}`")

    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Aᴅᴅ Mᴇ Tᴏ Gʀᴏᴜᴘ", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("Hᴇʟᴘ", callback_data="help"), InlineKeyboardButton("Aʙᴏᴜᴛ", callback_data="about")],
        [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL), InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
    ])
    
    await emoji_msg.delete()
    await message.reply_photo(image, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@app.on_message(filters.new_chat_members)
async def welcome_group(client, message: Message):
    for user in message.new_chat_members:
        if user.id == (await client.get_me()).id:  # Check if it's the bot
            group_title = message.chat.title
            group_link = f"https://t.me/c/{str(message.chat.id)[4:]}" if str(message.chat.id).startswith("-100") else "https://t.me/"
            text = f"TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇh Tᴏ <a href=\"{group_link}\">{group_title}</a>, Lᴇᴛs Sᴛᴀʀᴛ Tʜᴇ Gᴀᴍᴇ...😂"
            await message.reply_text(text, parse_mode=ParseMode.HTML)
            
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    if not message.caption:
        return
    file_name = message.caption.strip().lower()
    file_doc = {
        "file_name": file_name,
        "chat_id": message.chat.id,
        "message_id": message.message_id,
        "language": "English"
    }
    files_col.insert_one(file_doc)

@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about", "delete"]) & ~filters.bot)
async def search_file(client, message: Message):
    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Jᴏɪɴ Nᴏᴡ!", url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("Jᴏɪɴᴇᴅ", callback_data="checksub")]
        ])
        return await message.reply("Tᴏ Usᴇ Tʜɪs Bᴏᴛ, Pʟᴇᴀsᴇ Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ Fɪʀsᴛ.", reply_markup=keyboard)

    query = message.text.strip().lower()
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))
    if not results:
        return

    markup = generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id)
    await message.reply(
    f"<blockquote>Hᴇʟʟᴏ! <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\n"
    f"🎁Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ <code>{message.text.strip()}</code>",
    reply_markup=markup,
    parse_mode=ParseMode.HTML
)
    
@app.on_callback_query()
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data

    if data.startswith(("search:", "movie:")):
        prefix, page_str, query_text = data.split(":", 2)
        page = int(page_str)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}}))
        markup = generate_pagination_buttons(results, (await client.get_me()).username, page, 5, prefix, query_text, query.from_user.id)
        return await query.message.edit_reply_markup(markup)

    elif data == "help":
        await query.message.edit_text("Wᴇʟᴄᴏᴍᴇ! Tᴏ Mʏ Sᴛᴏʀᴇ\n\n<blockquote>Nᴏᴛᴇ: Uɴᴅᴇʀ Cᴏɴsᴛʀᴜᴄᴛɪᴏɴ 🚧</blockquote>", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data="back")]]))
        return await query.answer()

    elif data == "about":
        bot_username = (await client.get_me()).username
        about_text = (
            f"""- - - - - - 🍿Aʙᴏᴜᴛ Mᴇʜ - - - - - -

-ˋˏ✄- - Iᴍ Aɴ <a href='https://t.me/{bot_username}'>Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</a>
-ˋˏ✄- - Bᴜɪʟᴛ Wɪᴛʜ 💌 <a href='https://www.python.org/'>Pʏᴛʜᴏɴ</a> & 
-ˋˏ✄- - <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ</a>
-ˋˏ✄- - Dᴀᴛᴀʙᴀsᴇ : <a href='https://www.mongodb.com/'>MᴏɴɢᴏDB</a>
-ˋˏ✄- - Bᴏᴛ Sᴇʀᴠᴇʀ : <a href='https://Render.com/'>Rᴇɴᴅᴇʀ</a>"""
        )
        await query.message.edit_text(
            about_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Lᴏʀᴅ", url="https://t.me/GandhiNote"), InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data="back")]
            parse_mode=ParseMode.HTML
        )
        return await query.answer()

    elif data == "back":
        image = random.choice(IMAGE_URLS)
        caption = random.choice(CAPTIONS).format(user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>')
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Aᴅᴅ Mᴇ Tᴏ Gʀᴏᴜᴘ", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
            [InlineKeyboardButton("Hᴇʟᴘ", callback_data="help"), InlineKeyboardButton("Aʙᴏᴜᴛ", callback_data="about")],
            [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL), InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
        ])
        try:
            await query.message.edit_media(InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML), reply_markup=keyboard)
        except:
            await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return await query.answer()

    elif data == "checksub":
        if await check_subscription(client, query.from_user.id):
            await query.message.edit_text("Jᴏɪɴᴇᴅ")
        else:
            await query.answer("Tᴏ Usᴇ Tʜɪs Bᴏᴛ, Pʟᴇᴀsᴇ Jᴏɪɴ Oᴜʀ Cʜᴀɴɴᴇʟ Fɪʀsᴛ.", show_alert=True)

    elif data == "noop":
        return await query.answer()

    elif data.startswith("deletefile:"):
        file_id = data.split(":")[1]
        result = files_col.find_one({"_id": ObjectId(file_id)})
        if result:
            files_col.delete_one({"_id": ObjectId(file_id)})
            await query.answer("✅ File deleted.")
            await query.message.delete()
        else:
            await query.answer("❌ File not found.", show_alert=True)

# Remaining functions: welcome, stats, tracking

@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    users = users_col.count_documents({})
    groups = groups_col.count_documents({})
    files = files_col.count_documents({})
    await message.reply(f"- - - - - - 🍿Bᴏᴛ Sᴛᴀᴛs - - - - - --\nˋˏ✄- Tᴏᴛᴀʟ Usᴇʀs: {users}\n-ˋˏ✄- Tᴏᴛᴀʟ Cʜᴀᴛs: {groups}\n-ˋˏ✄- Tᴏᴛᴀʟ Fɪʟᴇs: {files}")

@app.on_message(filters.private & filters.text)
async def track_user(client, message: Message):
    users_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"name": message.from_user.first_name}},
        upsert=True
    )

@app.on_message(filters.group & filters.text)
async def track_group(client, message: Message):
    groups_col.update_one(
        {"_id": message.chat.id},
        {"$set": {"title": message.chat.title}},
        upsert=True
    )

print("Bot is starting...")
app.run()
