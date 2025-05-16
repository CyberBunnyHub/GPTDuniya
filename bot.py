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
    smallcaps_map = {
        'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ғ', 'g': 'ɢ',
        'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
        'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 's', 't': 'ᴛ', 'u': 'ᴜ',
        'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
    }

    def smallcap_char(c):
        return smallcaps_map.get(c.lower(), c)

    def process_word(word):
        if not word:
            return word
        first = word[0].upper()
        rest = ''.join(smallcap_char(c) for c in word[1:])
        return first + rest

    return ' '.join(process_word(word) for word in text.split())

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
        nav_buttons.append(InlineKeyboardButton("⟲ Bᴀᴄᴋ", callback_data=f"{prefix}:{page - 1}:{query}"))
    nav_buttons.append(InlineKeyboardButton(f"Page {page + 1}/{total_pages}", callback_data="noop"))
    if end < len(results):
        nav_buttons.append(InlineKeyboardButton("Nᴇxᴛ ⇌", callback_data=f"{prefix}:{page + 1}:{query}"))

    if nav_buttons:
        buttons.append(nav_buttons)

    return InlineKeyboardMarkup(buttons)

@app.on_message(filters.command("start") & filters.private)
async def start_cmd(client, message: Message):
    emoji_msg = await message.reply("🍿")
    image = random.choice(IMAGE_URLS)
    user_mention = f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    caption = random.choice(CAPTIONS).format(user_mention=user_mention)

    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(to_smallcaps_title("Join Now!"), url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton(to_smallcaps_title("Joined"), callback_data="checksub")]
        ])
        await emoji_msg.delete()
        return await message.reply(to_smallcaps_title("To use this bot, please join our channel first."), reply_markup=keyboard)

    args = message.text.split()
    if len(args) > 1:
        try:
            doc = files_col.find_one({"_id": ObjectId(args[1])})
            await emoji_msg.delete()
            if not doc:
                return await message.reply(to_smallcaps_title("❌ File not found."))
            return await client.copy_message(chat_id=message.chat.id, from_chat_id=doc["chat_id"], message_id=doc["message_id"])
        except Exception as e:
            await emoji_msg.delete()
            return await message.reply(to_smallcaps_title(f"❌ Error retrieving file:\n\n{e}"))

    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(to_smallcaps_title("Add Me To Group"), url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton(to_smallcaps_title("⇋ Help"), callback_data="help"), InlineKeyboardButton(to_smallcaps_title("About ⇌"), callback_data="about")],
        [InlineKeyboardButton(to_smallcaps_title("Updates"), url=UPDATE_CHANNEL), InlineKeyboardButton(to_smallcaps_title("Support"), url=SUPPORT_GROUP)]
    ])

    await emoji_msg.delete()
    await message.reply_photo(image, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about"]) & ~filters.bot)
async def search_file(client, message: Message):
    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(to_smallcaps_title("Join Now!"), url=f"https://t.me/{UPDATE_CHANNEL.lstrip('@')}")],
            [InlineKeyboardButton(to_smallcaps_title("Joined"), callback_data="checksub")]
        ])
        return await message.reply(to_smallcaps_title("To use this bot, please join our channel first."), reply_markup=keyboard)

    query = message.text.strip().lower()
    results = list(files_col.find({"file_name": {"$regex": query, "$options": "i"}}))
    if not results:
        return

    markup = generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id)
    await message.reply(
        to_smallcaps_title(f"<blockquote>Hello <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\nHere is what I found for your search: <code>{message.text.strip()}</code>"),
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
        return await query.message.edit_text(to_smallcaps_title("""Welcome To My Store!\n\n
        <blockquote>Note: Under Construction...🚧</blockquote>"""), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(to_smallcaps_title("⟲ Back"), callback_data="back")]]))

    elif data == "about":
        bot_username = (await client.get_me()).username
        about_text = f"""- - - - - - 🍿 {to_smallcaps_title("About Me")} - - - - - -

{to_smallcaps_title("-ˋˏ✄- - Iᴍ Aɴ <a href='https://t.me/{bot_username}'>Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</a>")}
{to_smallcaps_title("-ˋˏ✄- - Bᴜɪʟᴛ Wɪᴛʜ 💌 <a href='https://www.python.org/'>Pʏᴛʜᴏɴ</a> & \n-ˋˏ✄- - <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ</a>")}
{to_smallcaps_title("-ˋˏ✄- - Dᴀᴛᴀʙᴀsᴇ : <a href='https://www.mongodb.com/'>MᴏɴɢᴏDB</a>")}
{to_smallcaps_title(" -ˋˏ✄- - Bᴏᴛ Sᴇʀᴠᴇʀ : <a href='https://Render.com/'>Rᴇɴᴅᴇʀ</a>")}"""
        await query.message.edit_text(
            about_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton(to_smallcaps_title("Lord"), url="https://t.me/GandhiNote"),                 InlineKeyboardButton(to_smallcaps_title("⟲ Back"), callback_data="back")]
            ]),
            parse_mode=ParseMode.HTML
        )

    elif data == "back":
        image = random.choice(IMAGE_URLS)
        caption = random.choice(CAPTIONS).format(user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>')
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(to_smallcaps_title("Add Me To Group"), url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
            [InlineKeyboardButton(to_smallcaps_title("⇋ Help"), callback_data="help"), InlineKeyboardButton(to_smallcaps_title("About ⇌"), callback_data="about")],
            [InlineKeyboardButton(to_smallcaps_title("Updates"), url=UPDATE_CHANNEL), InlineKeyboardButton(to_smallcaps_title("Support"), url=SUPPORT_GROUP)]
        ])
        try:
            await query.message.edit_media(InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML), reply_markup=keyboard)
        except:
            await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

    elif data == "checksub":
        if await check_subscription(client, query.from_user.id):
            await query.message.edit_text(to_smallcaps_title("Joined!"))
        else:
            await query.answer(to_smallcaps_title("Please join the updates channel to use this bot."), show_alert=True)

    elif data == "noop":
        await query.answer()

    elif data.startswith("deletefile:"):
        file_id = data.split(":")[1]
        result = files_col.find_one({"_id": ObjectId(file_id)})
        if result:
            files_col.delete_one({"_id": ObjectId(file_id)})
            await query.answer(to_smallcaps_title("✅ File deleted."))
            await query.message.delete()
        else:
            await query.answer(to_smallcaps_title("❌ File not found."), show_alert=True)

@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    users = users_col.count_documents({})
    groups = groups_col.count_documents({})
    files = files_col.count_documents({})
    await message.reply(to_smallcaps_title(f"""- - - - - - 📉 Bot Stats - - - - - -\n
    Total Users: {users}\n
    Total Groups: {groups}\n
    Total Files: {files}"""))

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

@app.on_message(filters.new_chat_members)
async def welcome_group(client, message: Message):
    for user in message.new_chat_members:
        if user.id == (await client.get_me()).id:  # Check if it's the bot
            group_title = message.chat.title
            group_link = f"https://t.me/c/{str(message.chat.id)[4:]}" if str(message.chat.id).startswith("-100") else "https://t.me/"
            
            caption = (to_smallcaps_title(
                f"TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇʜ Tᴏ <a href=\"{group_link}\">{group_title}</a>\n\n"
                f"Lᴇᴛ’s Get Started..."
            ))

            keyboard = InlineKeyboardMarkup(to_smallcaps_title([
                [InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP), InlineKeyboardButton("Updates", url=UPDATE_CHANNEL)]
            ]))

            await message.reply_text(caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    if not message.caption:
        return
    file_name = message.caption.strip().lower()
    file_doc = {
        "file_name": file_name,
        "chat_id": message.chat.id,
        "message_id": message.id,
        "language": "English"
    }
    files_col.insert_one(file_doc)

elif data.startswith("langs:"):
        _, query_text, _ = data.split(":", 2)
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}}))
        languages = sorted(set(doc.get("language", "Unknown") for doc in results))

        if not languages:
            return await query.answer("No language info available.", show_alert=True)

        buttons = [
            [InlineKeyboardButton(to_smallcaps_title(lang), callback_data=f"langselect:{query_text}:{lang}")]
            for lang in languages
        ]
        buttons.append([InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data=f"search:0:{query_text}")])
        markup = InlineKeyboardMarkup(buttons)

        await query.message.edit_text(
            f"Sᴇʟᴇᴄᴛ A Lᴀɴɢᴜᴀɢᴇ Fᴏʀ: <code>{query_text}</code>",
            reply_markup=markup,
            parse_mode=ParseMode.HTML
        )
        return await query.answer()

elif data.startswith("langselect:"):
        _, query_text, selected_lang = data.split(":", 2)
        results = list(files_col.find({
            "file_name": {"$regex": query_text, "$options": "i"},
            "language": selected_lang
        }))

        if not results:
            return await query.message.edit_text(f"Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}.", parse_mode=ParseMode.HTML)

        markup = generate_pagination_buttons(
            results, (await client.get_me()).username, 0, 5, "search", query_text, query.from_user.id
        )
        await query.message.edit_text(
            f"Fɪʟᴇs Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}:", parse_mode=ParseMode.HTML, reply_markup=markup
        )
        return await query.answer()

print("Bot is starting...")
app.run()
