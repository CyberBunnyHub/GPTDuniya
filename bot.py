import asyncio
import random
import re
import base64
from bson import ObjectId
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, UserNotParticipant, FloodWait
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)

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
    return re.sub(r"[^\w\s]", " ", text).lower().strip()


async def check_subscription(client, user_id):
    try:
        member = await client.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except UserNotParticipant:
        return False
    except Exception:
        return True


def extract_language(text):
    languages = ["hindi", "telugu", "tamil", "malayalam", "kannada", "english", "bengali"]
    for lang in languages:
        if lang in text.lower():
            return lang.capitalize()
    return "Unknown"


def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query="", user_id=None, selected_lang="All"):
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
        # Check again to ensure file still exists (optional redundancy)
        if not files_col.find_one({"_id": doc["_id"]}):
            continue  # Skip if file is not in the database anymore

        row = [InlineKeyboardButton(
            f"🎬 {doc.get('file_name', 'Unnamed')[:30]}",
            url=f"https://t.me/{bot_username}?start={doc['_id']}"
        )]
        if user_id == BOT_OWNER:
            row.append(InlineKeyboardButton("✘", callback_data=f"deletefile:{doc['_id']}"))
        buttons.append(row)

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

    # Check subscription
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
            caption = f"<code>{original_message.caption or doc.get('file_name', 'No Caption')}</code>"

            await client.send_document(
                chat_id=message.chat.id,
                document=original_message.document.file_id,
                caption=caption,
                parse_mode=ParseMode.HTML
            )

            return  # ✅ Stop execution after sending the file

        except Exception as e:
            await emoji_msg.delete()
            return await message.reply(f"❌ Error retrieving file:\n\n{e}")

    # Default /start message
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
        await message.reply("To use this bot, please join our channel first.", reply_markup=keyboard)
        return  # <-- Exit early if not subscribed

    # Only runs if subscribed
    user_query = message.text.strip()
    query = normalize_text(user_query)

    # Search all results regardless of language
    results = list(files_col.find({
        "normalized_name": {"$regex": query, "$options": "i"}
    }))

    if not results:
        return  # Stay silent if nothing found (as per your earlier preference)

    markup = generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id)
    await message.reply(
        f"<blockquote>Hello <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\nHere is what I found for your search: <code>{message.text.strip()}</code>",
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )


@app.on_callback_query()
async def handle_callbacks(client, query: CallbackQuery):
    data = query.data
    try:
        # Pagination and search callback
        if data.startswith("search:") or data.startswith("movie:"):
            parts = data.split(":", 3)
            if len(parts) == 4:
                prefix, page_str, query_text, lang = parts
            else:
                prefix, page_str, query_text = parts
                lang = None  # fallback if language not provided

            page = int(page_str)
            normalized_query = normalize_text(query_text)
            query_filter = {
                "normalized_name": {"$regex": normalized_query, "$options": "i"}
            }
            if lang and lang != "All":
                query_filter["language"] = lang.capitalize()

            results = list(files_col.find(query_filter))

            if not results:
                return await query.answer("No files found.", show_alert=True)

            markup = generate_pagination_buttons(
                results, (await client.get_me()).username, page, 5,
                prefix, query_text, query.from_user.id, lang or "All"
            )

            try:
                await query.message.edit_reply_markup(markup)
            except MessageNotModified:
                pass
            return await query.answer()

        # Delete file
        elif data.startswith("deletefile:"):
            file_id = data.split(":")[1]
            result = files_col.find_one({"_id": ObjectId(file_id)})
            if result:
                files_col.delete_one({"_id": ObjectId(file_id)})
                await query.answer("✅ File deleted.")
                return await query.message.delete()
            else:
                return await query.answer("❌ File not found.", show_alert=True)

        # Help
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

        # Database
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

        # Check subscription
        elif data == "checksub":
            if await check_subscription(client, query.from_user.id):
                return await query.message.edit_text("Joined!")
            else:
                return await query.answer("Please join the updates channel to use this bot.", show_alert=True)

        # Get files for current page, language
        elif data.startswith("getfiles:"):
            parts = data.split(":")
            query_text = parts[1]
            page_str = parts[2]
            selected_lang = parts[3] if len(parts) > 3 else "All"
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

        # About
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

        # Show statistics
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

        # Go back to main menu
        elif data == "back":
            image = random.choice(IMAGE_URLS)
            caption = random.choice(CAPTIONS).format(
                user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>'
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
                [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
                [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
            ])
            try:
                return await query.message.edit_media(InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML), reply_markup=keyboard)
            except Exception:
                try:
                    return await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)
                except Exception:
                    pass

        # Show language filter menu
        elif data.startswith("langs:"):
            _, query_text, _ = data.split(":", 2)
            encoded_query = base64.urlsafe_b64encode(query_text.encode()).decode()
            buttons = [[InlineKeyboardButton(lang, callback_data=f"langselect:{encoded_query}:{lang}")]
                       for lang in PREDEFINED_LANGUAGES]
            buttons.append([InlineKeyboardButton("</Bᴀᴄᴋ>", callback_data=f"search:0:{query_text}")])
            markup = InlineKeyboardMarkup(buttons)
            await query.message.edit_text(
                f"Sᴇʟᴇᴄᴛ A Lᴀɴɢᴜᴀɢᴇ Fᴏʀ: <code>{query_text}</code>",
                reply_markup=markup,
                parse_mode=ParseMode.HTML
            )
            return await query.answer()

        # Language selection for search
        elif data.startswith("langselect:"):
            parts = data.split(":", 2)
            if len(parts) < 3:
                return await query.answer("Invalid language selection.", show_alert=True)

            _, encoded_query, selected_lang = parts
            try:
                query_text = base64.urlsafe_b64decode(encoded_query.encode()).decode()
                selected_lang = selected_lang.capitalize()

                results = list(files_col.find({
                    "normalized_name": {"$regex": normalize_text(query_text), "$options": "i"},
                    "language": selected_lang
                }))

                if not results:
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⟲ Back", callback_data=f"search:0:{query_text}")]])
                    return await query.message.edit_text(
                        f"Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}.",
                        parse_mode=ParseMode.HTML,
                        reply_markup=markup
                    )

                markup = generate_pagination_buttons(
                    results, (await client.get_me()).username, 0, 5, "search", query_text, query.from_user.id, selected_lang
                )
                try:
                    await query.message.edit_text(
                        f"Fɪʟᴇs Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}:",
                        parse_mode=ParseMode.HTML,
                        reply_markup=markup
                    )
                except MessageNotModified:
                    pass
                return await query.answer()
            except Exception as e:
                print("Language selection error:", e)
                return await query.answer("Something went wrong.", show_alert=True)

        else:
            return await query.answer("Unknown action.", show_alert=True)

    except Exception as e:
        print(f"Error in callback: {e}")
        await query.answer("An error occurred.", show_alert=True)


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


@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    media = message.document or message.video
    file_name = media.file_name or "Unknown"
    caption = message.caption or ""
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
        "chat_id": message.chat.id,
        "message_id": message.id
    })
    print(f"Stored file: {file_name} | Language: {language}")


@app.on_message(filters.private & filters.forwarded)
async def process_forwarded_message(client, message: Message):
    if not message.forward_from_chat or not message.forward_from_message_id:
        await message.reply_text("Please forward the last message from a channel with quotes.")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id
    count = 0
    live_message = await message.reply_text("Scanning files... 0 found")

    for msg_id in range(last_msg_id, 0, -1):
        try:
            msg = await client.get_messages(chat_id, msg_id)
            if not msg:
                continue

            media = msg.document or msg.video
            if not media:
                continue  # skip messages without document/video

            file_name = media.file_name or "Unknown"
            caption = msg.caption or ""
            combined_text = f"{file_name} {caption}".lower()
            normalized_name = normalize_text(file_name)
            file_size = media.file_size
            mime_type = media.mime_type
            language = extract_language(combined_text)
            file_type = "document" if msg.document else "video"

            # Skip if file_id is not present
            if not hasattr(media, "file_id") or not media.file_id:
                continue

            # Check for duplicate (by chat_id and message_id)
            existing = files_col.find_one({
                "chat_id": chat_id,
                "message_id": msg.id
            })
            if existing:
                continue

            files_col.insert_one({
                "file_name": file_name,
                "normalized_name": normalized_name,
                "language": language,
                "file_type": file_type,
                "mime_type": mime_type,
                "file_size": file_size,
                "file_id": media.file_id,
                "chat_id": chat_id,
                "message_id": msg.id
            })

            count += 1
            new_text = f"Scanning files... {count} found"
            if live_message.text != new_text:
                try:
                    await live_message.edit_text(new_text)
                except MessageNotModified:
                    pass

        except Exception as e:
            print(f"Error at message {msg_id}: {e}")
            break

    final_text = f"✅ Done! {count} files added."
    if live_message.text != final_text:
        try:
            await live_message.edit_text(final_text)
        except MessageNotModified:
            pass
            
            for msg_id in range(last_msg_id, max(last_msg_id-100, 0), -1):
                msg = await client.get_messages(chat_id, msg_id)
                print(f"msg_id={msg_id}, document={getattr(msg, 'document', None)}, video={getattr(msg, 'video', None)}, video_note={getattr(msg, 'video_note', None)}, media_group_id={getattr(msg, 'media_group_id', None)}")

print("starting...")
app.run()
