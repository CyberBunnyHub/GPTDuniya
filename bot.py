import asyncio
import random
import re
import base64
from bson import ObjectId
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)
from pyrogram.errors import UserNotParticipant, FloodWait

from config import (
    BOT_TOKEN, API_ID, API_HASH, BOT_OWNER, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, SUPPORT_GROUP
)

PREDEFINED_LANGUAGES = ["Kannada", "English", "Hindi", "Tamil", "Telugu", "Malayalam"]

app = Client("AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

def normalize_text(text):
    return re.sub(r'\W+', '', text.lower())

async def check_subscription(client, user_id):
    try:
        member = await client.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except UserNotParticipant:
        return False
    except:
        return True
async def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query="", user_id=None, selected_lang="All"):
    total_pages = (len(results) + per_page - 1) // per_page
    start = page * per_page
    end = start + per_page
    page_data = results[start:end]

    if not page_data and results:
        page = 0
        start = 0
        end = per_page
        page_data = results[start:end]

    buttons = []
    for doc in page_data:
        try:
            await app.get_messages(doc["chat_id"], doc["message_id"])
            row = [InlineKeyboardButton(
                f"🎬 {doc.get('file_name', 'Unnamed')[:30]}",
                url=f"https://t.me/{bot_username}?start={doc['_id']}"
            )]
            if user_id == BOT_OWNER:
                row.append(InlineKeyboardButton("✘", callback_data=f"deletefile:{doc['_id']}"))
            buttons.append(row)
        except:
            continue

    if buttons:
        buttons.append([
            InlineKeyboardButton("Gᴇᴛ Aʟʟ Fɪʟᴇs", callback_data=f"getfiles:{query}:{page}:{selected_lang}"),
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
            [InlineKeyboardButton("Join Now!", url=UPDATE_CHANNEL)],
            [InlineKeyboardButton("Joined", callback_data="checksub")]
        ])
        await emoji_msg.delete()
        return await message.reply("To use this bot, please join our channel first.", reply_markup=keyboard)

    args = message.text.split()
    if len(args) > 1:
        try:
            doc = files_col.find_one({"_id": ObjectId(args[1])})
            await emoji_msg.delete()
            if not doc:
                return await message.reply("❌ File not found.")
            original_message = await client.get_messages(doc["chat_id"], doc["message_id"])
            file_caption = f"<code>{original_message.caption or doc.get('file_name', 'No Caption')}</code>"
            await client.send_document(
                chat_id=message.chat.id,
                document=original_message.document.file_id,
                caption=file_caption,
                parse_mode=ParseMode.HTML
            )
            return  # <- IMPORTANT: stop further execution after sending the file

        except Exception as e:
            await emoji_msg.delete()
            return await message.reply(f"❌ Error retrieving file:\n\n{e}")

    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
        [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
    ])

    await emoji_msg.delete()
    await message.reply_photo(image, caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    
@app.on_message(filters.private & filters.text & ~filters.command(["start", "stats", "help", "about"]) & ~filters.bot)
async def search_and_track(client, message: Message):
    users_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"name": message.from_user.first_name}},
        upsert=True
    )

    if not await check_subscription(client, message.from_user.id):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("Join Now!", url=UPDATE_CHANNEL)],
            [InlineKeyboardButton("Joined", callback_data="checksub")]
        ])
        return await message.reply("To use this bot, please join our channel first.", reply_markup=keyboard)

    query = message.text.strip()
    normalized_query = normalize_text(query)
    results = list(files_col.find({
        "normalized_name": {"$regex": normalized_query, "$options": "i"}
    }))

    if not results:
        return

    reply_markup = await generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id)
    await message.reply(
        f"<b><blockquote>Hello <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote></b>\n\nHere is what I found for your search: <code>{message.text.strip()}</code>",
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query()
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data

    if data.startswith(("search:", "movie:")):
        prefix, page_str, query_text = data.split(":", 2)
        page = int(page_str)
        normalized_query = normalize_text(query_text)
        results = list(files_col.find({
            "normalized_name": {"$regex": normalized_query, "$options": "i"}
        }))
        
        if not results:
            return await query.answer("No files found.", show_alert=True)

        markup = await generate_pagination_buttons(results, (await client.get_me()).username, page, 5, prefix, query_text, query.from_user.id)
        await query.message.edit_reply_markup(markup)
        return await query.answer()

    elif data.startswith("deletefile:"):
        file_id = data.split(":")[1]
        result = files_col.find_one({"_id": ObjectId(file_id)})
        if result:
            files_col.delete_one({"_id": ObjectId(file_id)})
            await query.answer("✅ File deleted.")
            return await query.message.delete()
        else:
            return await query.answer("❌ File not found.", show_alert=True)

    elif data == "help":
        return await query.message.edit_text(
            "Welcome To My Store!\n\n<blockquote>Note: Under Construction...🚧</blockquote>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Stats", callback_data="showstats")],
                [InlineKeyboardButton("🗂 Database", callback_data="database")],
                [InlineKeyboardButton("⟲ Back", callback_data="back")]
            ]),
            parse_mode=ParseMode.HTML
        )

    elif data == "database":
        db_help_text = (
            "<b>- - - - - - 🗂 How to Add Files - - - - - -</b>\n\n"
            "1. ᴍᴀᴋᴇ ᴍᴇ ᴀɴ ᴀᴅᴍɪɴ ɪɴ ʏᴏᴜʀ ᴄʜᴀɴɴᴇʟ ɪꜰ ɪᴛ'ꜱ ᴘʀɪᴠᴀᴛᴇ.\n"
            "2. ꜰᴏʀᴡᴀʀᴅ ᴛʜᴇ ʟᴀꜱᴛ ᴍᴇꜱꜱᴀɢᴇ ᴏꜰ ᴛʜᴇ ᴄʜᴀɴɴᴇʟ ᴡɪᴛʜ ϙᴜᴏᴛᴇꜱ.\n"
            "I'ʟʟ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ᴀᴅᴅ ᴀʟʟ ꜰɪʟᴇꜱ ᴛᴏ ᴍʏ ᴅᴀᴛᴀʙᴀꜱᴇ!"
        )
        await query.message.edit_text(
            db_help_text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⟲ Back", callback_data="help")]]),
            parse_mode=ParseMode.HTML
        )

    elif data == "checksub":
        if await check_subscription(client, query.from_user.id):
            return await query.message.edit_text("Joined!")
        else:
            return await query.answer("Please join the updates channel to use this bot.", show_alert=True)

    elif data.startswith("getfiles:"):
        parts = data.split(":")
        query_text = parts[1]
        page_str = parts[2]
        selected_lang = parts[3] if len(parts) > 3 else None
        page = int(page_str)
        per_page = 5

        query_filter = {"normalized_name": {"$regex": normalize_text(query_text), "$options": "i"}}
        if selected_lang and selected_lang != "All":
            query_filter["language"] = selected_lang.capitalize()
        results = list(files_col.find(query_filter))

        selected_docs = results[page * per_page: (page + 1) * per_page]

        if not selected_docs:
            return await query.answer("No files found on this page.", show_alert=True)

        await query.answer("Sending selected files...")
        for doc in selected_docs:
            try:
                original_message = await client.get_messages(doc["chat_id"], doc["message_id"])
                caption = f"<code>{original_message.caption or doc.get('file_name', 'No Caption')}</code>"
                await client.send_document(
                    chat_id=query.message.chat.id,
                    document=original_message.document.file_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(0.5)
            except FloodWait as e:
                await asyncio.sleep(e.value)
            except Exception as e:
                print(f"Failed to send file: {e}")

    elif data == "about":
        bot_username = (await client.get_me()).username
        about_text = f"""- - - - - - 🍿About Me - - - - - -
-ˋˏ✄- - Iᴍ Aɴ <a href='https://t.me/{bot_username}'>Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</a>
-ˋˏ✄- - Bᴜɪʟᴛ Wɪᴛʜ 💌 <a href='https://www.python.org/'>Pʏᴛʜᴏɴ</a> & <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ</a>
-ˋˏ✄- - Dᴀᴛᴀʙᴀsᴇ : <a href='https://www.mongodb.com/'>MᴏɴɢᴏDB</a>
-ˋˏ✄- - Bᴏᴛ Sᴇʀᴠᴇʀ : <a href='https://Render.com/'>Rᴇɴᴅᴇʀ</a>
"""
        return await query.message.edit_text(
            about_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Lord", url="https://t.me/GandhiNote"),
                 InlineKeyboardButton("⟲ Back", callback_data="back")]
            ]),
            parse_mode=ParseMode.HTML
        )

    elif data == "showstats":
        users = users_col.count_documents({})
        groups = groups_col.count_documents({})
        files = files_col.count_documents({})
        return await query.message.edit_text(
            f"""<b>- - - - - - 📉 Bot Stats - - - - - -</b>
<b>Total Users:</b> {users}
<b>Total Groups:</b> {groups}
<b>Total Files:</b> {files}
""",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="showstats")],
                [InlineKeyboardButton("⟲ Back", callback_data="help")]
            ]),
            parse_mode=ParseMode.HTML
        )

    elif data == "back":
        bot_username = (await client.get_me()).username
        image = random.choice(IMAGE_URLS)
        caption = random.choice(CAPTIONS).format(user_mention=f"<a href='tg://user?id={query.from_user.id}'>{query.from_user.first_name}</a>")
        return await query.message.edit_media(
            media=InputMediaPhoto(media=image, caption=caption, parse_mode=ParseMode.HTML),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{bot_username}?startgroup=true")],
                [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
                [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
            ])
        )
        
    elif data.startswith("langs:"):
        query_text = data.split(":", 1)[1]
        query_filter = {
            "normalized_name": {"$regex": normalize_text(query_text), "$options": "i"}
        }
        available_languages = files_col.distinct("language", query_filter)
        available_languages = sorted([lang for lang in available_languages if lang])

        if not available_languages:
            return await query.answer("No languages found for this title.", show_alert=True)

        lang_buttons = []
        for lang in available_languages:
            lang_buttons.append([
                InlineKeyboardButton(lang, callback_data=f"getfiles:{query_text}:0:{lang}")
            ])

        lang_buttons.append([
            InlineKeyboardButton("Back", callback_data=f"search:{query_text}:0")
        ])

        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(lang_buttons)
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
        if user.id == (await client.get_me()).id:
            group_title = message.chat.title
            group_link = f"https://t.me/c/{str(message.chat.id)[4:]}" if str(message.chat.id).startswith("-100") else "https://t.me/"
            caption = (
                f"TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇʜ Tᴏ <a href=\"{group_link}\">{group_title}</a>\n\n"
                f"Lᴇᴛ’s Get Started..."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP), InlineKeyboardButton("Updates", url=UPDATE_CHANNEL)]
            ])
            await message.reply_text(caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

def extract_language(text):
    text = text.lower()
    languages = ["hindi", "telugu", "tamil", "kannada", "malayalam", "english"]
    for lang in languages:
        if f" {lang} " in f" {text} ":
            return lang.capitalize()
    return "Unknown"
    
@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    media = message.document or message.video
    file_name = media.file_name
    caption = msg.caption or ""
    combined_text = f"{file_name} {caption}".lower()
    normalized_name = normalize_text(file_name)
    language = extract_language(combined_text)

    # Check for duplicate
    existing = files_col.find_one({
        "chat_id": message.chat.id,
        "message_id": message.id
    })
    if existing:
        print(f"Skipped duplicate: {file_name}")
        return

    files_col.insert_one({
        "file_name": file_name,
        "normalized_name": normalized_name,
        "language": language,
        "chat_id": chat_id,
        "message_id": message.id
    })
    print(f"Stored file: {file_name} | Language: {language}")

@app.on_message(filters.private & filters.forwarded)
async def handle_forwarded_channel_message(client, message: Message):
    if not message.forward_from_chat or message.forward_from_chat.type.name != "CHANNEL":
        return await message.reply("❌ Please forward a message from a channel.")

    try:
        chat_id = message.forward_from_chat.id
        offset_id = message.forward_from_message_id
        total = 0
        batch_size = 100

        status_msg = await message.reply("⏳ Starting file scan...")

        while True:
            messages = await client.get_chat_history(chat_id, offset_id=offset_id, limit=batch_size)
            messages = list(messages)  # convert async generator to list
            if not messages:
                break

            found_any = False

            for msg in messages:
                offset_id = msg.id  # update offset for next batch

                if not msg or not (msg.document or msg.video):
                    continue

                media = msg.document or msg.video
                if not media or not media.file_id:
                    continue  # skip if file_id is missing

                file_name = media.file_name or "Unnamed"
                caption = msg.caption or ""
                combined_text = f"{file_name} {caption}".lower()
                normalized_name = normalize_text(file_name)
                language = extract_language(combined_text)

                existing = files_col.find_one({
                    "chat_id": msg.chat.id,
                    "message_id": msg.id
                })

                if existing:
                    continue

                files_col.insert_one({
                    "file_name": file_name,
                    "normalized_name": normalized_name,
                    "language": language,
                    "chat_id": msg.chat.id,
                    "message_id": msg.id
                })

                total += 1
                found_any = True

                if total % 10 == 0:
                    try:
                        await status_msg.edit_text(f"📦 Collected {total} files...")
                    except:
                        pass

            if not found_any:
                break

        final_msg = f"✅ {total} new files added to database." if total > 0 else "ℹ️ No new files found."
        await status_msg.edit_text(final_msg)

    except Exception as e:
        await message.reply(f"❌ Failed to add files.\n\nError: `{e}`")

print("starting...")
app.run()
