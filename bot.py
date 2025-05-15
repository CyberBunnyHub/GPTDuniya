from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.errors import UserNotParticipant
from pymongo import MongoClient
from bson import ObjectId
from pyrogram.enums import ParseMode
import random
from pyrogram.types import InputMediaPhoto

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
            row.append(InlineKeyboardButton("❌", callback_data=f"deletefile:{doc['_id']}"))
        buttons.append(row)

    if results:
        buttons.append([
            InlineKeyboardButton("📂 Get All Files", callback_data=f"getfiles:{query}"),
            InlineKeyboardButton("🌐 Language", callback_data=f"langs:{query}:dummy")
        ])

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"{prefix}:{page - 1}:{query}"))
    nav_buttons.append(InlineKeyboardButton(f"Page {page + 1}/{total_pages}", callback_data="noop"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton("➡️ Next", callback_data=f"{prefix}:{page + 1}:{query}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    image = random.choice(IMAGE_URLS)
    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    caption = random.choice(CAPTIONS).format(user_mention=user_mention)

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

@app.on_message(filters.new_chat_members)
async def welcome_new_members(client, message: Message):
    for member in message.new_chat_members:
        if member.id == (await client.get_me()).id:
            group_title = message.chat.title
            group_link = f"https://t.me/{message.chat.username}" if message.chat.username else "this group"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Uᴘᴅᴀᴛᴇs", url=UPDATE_CHANNEL),
                 InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP)]
            ])
            text = (
   f'TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇh Tᴏ <a herf ='{group_link}'>'{group_title}'</a>
Lᴇᴛs Sᴛᴀʀᴛ Tʜᴇ Gᴀᴍᴇ...😂'
            )
            await message.reply(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

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
    result = files_col.insert_one(file_doc)
    print(f"Saved file with ID: {result.inserted_id}")

@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about", "delete"]) & ~filters.bot)
async def search_file(client, message: Message):
    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Update Channel", url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton("✅ Joined", callback_data="checksub")]
        ])
        return await message.reply("🚫 To use this bot, please join our update channel first.", reply_markup=keyboard)

    query = message.text.strip().lower()
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))
    if not results:
        return

    markup = generate_pagination_buttons(results, (await client.get_me()).username, page=0, per_page=5, prefix="search", query=query, user_id=message.from_user.id)
    await message.reply("✅ Results found:", reply_markup=markup)

@app.on_callback_query()
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data

    if data.startswith(("search:", "movie:")):
        prefix, page_str, query_text = data.split(":", 2)
        page = int(page_str)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}}))
        markup = generate_pagination_buttons(results, (await client.get_me()).username, page, 5, prefix, query_text, query.from_user.id)
        try:
            await message.reply(
    f"<blockquote>Hᴇʟʟᴏ! <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\n"
    f"🎁Hᴇʀᴇ I Fᴏᴜɴᴅ Fᴏʀ Yᴏᴜʀ Sᴇᴀʀᴄʜ <code>{message.text.strip()}</code>",
    reply_markup=markup,
    parse_mode=ParseMode.HTML
            )
        except:
            pass
        return await query.answer()

    elif data == "help":
        await query.message.edit_text("""Wᴇʟᴄᴏᴍᴇ! Tᴏ Mʏ Sᴛᴏʀᴇ\n\n<blockquote>Nᴏᴛᴇ: Uɴᴅᴇʀ Cᴏɴsᴛʀᴜᴄᴛɪᴏɴ 🚧</blockquote>""", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data="back")]]))
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
        await query.message.edit_text(about_text, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Dᴇᴠ", url="t.me/GandhiNote", InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data="back")]]), parse_mode=ParseMode.HTML)
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
            try:
                await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            except:
                pass
        return await query.answer()

    elif data == "checksub":
        if await check_subscription(client, query.from_user.id):
            await query.message.edit_text("✅ You're subscribed! You can now use the bot.")
        else:
            await query.answer("❌ You're still not subscribed.", show_alert=True)

    elif data == "noop":
        await query.answer()

    elif data.startswith("langs:"):
        _, query_text, _ = data.split(":", 2)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}}))
        langs = sorted(set(doc.get("language", "Unknown") for doc in results))
        if not langs:
            return await query.answer("No languages found!", show_alert=True)

        lang_buttons = [[InlineKeyboardButton(lang, callback_data=f"filterlang:{query_text}:{lang}")] for lang in langs]
        await query.message.edit_text("Select language:", reply_markup=InlineKeyboardMarkup(lang_buttons))
        return await query.answer()

    elif data.startswith("filterlang:"):
        _, query_text, lang = data.split(":", 2)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}, "language": lang}))
        if not results:
            return await query.message.edit_text("No results in this language.")
        markup = generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query_text)
        return await query.message.edit_text(f"Results in {lang}:", reply_markup=markup)

    elif data.startswith("getfiles:"):
        parts = data.split(":", maxsplit=2)
        query_text = parts[1]
        lang = parts[2] if len(parts) > 2 else None

        search_filter = {"file_name": {"$regex": query_text, "$options": "i"}}
        if lang:
            search_filter["language"] = lang

        results = list(files_col.find(search_filter))
        if not results:
            return await query.answer("❌ No files found.", show_alert=True)

        for doc in results:
            try:
                await client.copy_message(query.message.chat.id, doc["chat_id"], doc["message_id"])
            except:
                continue
        return await query.answer(f"✅ Sent files{' in ' + lang if lang else ''}.")

    elif data.startswith("deletefile:"):
        file_id = data.split(":")[1]
        result = files_col.find_one({"_id": ObjectId(file_id)})
        if result:
            files_col.delete_one({"_id": ObjectId(file_id)})
            await query.answer("✅ File deleted.")
            await query.message.delete()
        else:
            await query.answer("❌ File not found.", show_alert=True)

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
