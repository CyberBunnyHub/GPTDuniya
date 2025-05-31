import asyncio
import random
import re
import base64
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, UserNotParticipant, FloodWait
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)
from flask import Flask
import os
import threading
from config import (
    BOT_TOKEN, API_ID, API_HASH, BOT_OWNER, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, SUPPORT_GROUP
)

PREDEFINED_LANGUAGES = ["Kannada", "English", "Hindi", "Tamil", "Telugu", "Malayalam"]

app = Client("CyberBunny", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]
user_channels_col = db["user_channels"]
logs_col = db["logs"]

# Flask setup for Render
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

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

async def log_event(event_type: str, user_id: int, chat_id: int = None, extra_data: dict = None):
    """Log an event to the database"""
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "timestamp": datetime.now(),
    }
    
    if chat_id:
        log_data["chat_id"] = chat_id
    if extra_data:
        log_data.update(extra_data)
    
    logs_col.insert_one(log_data)

async def generate_pagination_buttons(results, bot_username, page, per_page, prefix, query="", user_id=None, selected_lang="All", client=None):
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
        exists_in_db = files_col.find_one({"_id": doc["_id"]})
        exists_in_channel = False
        if exists_in_db and client is not None:
            try:
                await client.get_messages(doc["chat_id"], doc["message_id"])
                exists_in_channel = True
            except Exception:
                exists_in_channel = False
        if not (exists_in_db and exists_in_channel):
            continue

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
    # Check if this is a new user
    existing_user = users_col.find_one({"_id": message.from_user.id})
    if not existing_user:
        await log_event("new_user", message.from_user.id, extra_data={
            "username": message.from_user.username,
            "first_name": message.from_user.first_name,
            "last_name": message.from_user.last_name
        })
    
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
            if not doc:
                await emoji_msg.delete()
                return await message.reply("❌ File not found.")
            try:
                original_message = await client.get_messages(doc["chat_id"], doc["message_id"])
            except Exception:
                await emoji_msg.delete()
                return await message.reply("❌ File not found or has been deleted.")

            caption = f"<code>{original_message.caption or doc.get('file_name', 'No Caption')}</code>"

            if original_message.document:
                await client.send_document(
                    chat_id=message.chat.id,
                    document=original_message.document.file_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                await emoji_msg.delete()
                return

            elif original_message.video:
                await client.send_video(
                    chat_id=message.chat.id,
                    video=original_message.video.file_id,
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
                await emoji_msg.delete()
                return
            else:
                await emoji_msg.delete()
                return await message.reply("❌ File not found or unsupported media type.")

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

@app.on_message(filters.private & filters.text & ~filters.command(["start", "stats", "help", "about", "cleanup", "logs", "clearlogs"]) & ~filters.bot)
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
        return

    user_query = message.text.strip()
    query = normalize_text(user_query)

    results = list(files_col.find({
        "normalized_name": {"$regex": query, "$options": "i"}
    }))

    if not results:
        return

    markup = await generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id, client=client)
    await message.reply(
        f"<blockquote>Hello <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\nHere is what I found for your search: <code>{message.text.strip()}</code>",
        reply_markup=markup,
        parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("cleanup") & filters.user(BOT_OWNER))
async def cleanup_db(client, message: Message):
    await message.reply_text("🔍 Scanning for orphaned (deleted in channel) files, please wait...")
    deleted_count = 0
    for doc in files_col.find({}):
        try:
            await client.get_messages(DB_CHANNEL, doc["message_id"])
        except Exception:
            files_col.delete_one({"_id": doc["_id"]})
            deleted_count += 1
    await message.reply_text(f"✅ Cleanup complete. Deleted {deleted_count} orphaned file entries.")

@app.on_message(filters.command("logs") & filters.user(BOT_OWNER))
async def show_logs(client, message: Message):
    """Show recent logs"""
    args = message.text.split()
    limit = 20 if len(args) < 2 else min(int(args[1]), 100)
    
    logs = logs_col.find().sort("timestamp", -1).limit(limit)
    
    if not logs:
        return await message.reply("No logs found.")
    
    text = "📜 <b>Recent Logs</b>\n\n"
    for log in logs:
        timestamp = log["timestamp"].strftime("%Y-%m-%d %H:%M:%S")
        text += f"⏰ <b>{timestamp}</b>\n"
        text += f"🔹 <b>Event:</b> {log['event_type']}\n"
        
        if log["event_type"] == "new_user":
            user_info = f"👤 User: {log.get('first_name', '')} {log.get('last_name', '')}"
            if log.get("username"):
                user_info += f" (@{log['username']})"
            text += f"{user_info}\n"
            text += f"🆔 ID: <code>{log['user_id']}</code>\n"
        
        elif log["event_type"] == "new_group":
            text += f"👥 Group: {log.get('group_title', 'Unknown')}\n"
            text += f"🆔 ID: <code>{log['chat_id']}</code>\n"
            text += f"➕ Added by: <code>{log.get('added_by', 'Unknown')}</code>\n"
        
        text += "\n"
    
    await message.reply(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("clearlogs") & filters.user(BOT_OWNER))
async def clear_logs(client, message: Message):
    """Clear all logs"""
    if not message.text.endswith("--confirm"):
        return await message.reply(
            "⚠️ This will delete ALL logs. To confirm, run:\n"
            "<code>/clearlogs --confirm</code>"
        )
    
    result = logs_col.delete_many({})
    await message.reply(f"✅ Deleted {result.deleted_count} log entries.")

@app.on_message(filters.command("broadcast") & filters.user(BOT_OWNER))
async def broadcast_to_users(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("❌ Please reply to a message to broadcast")
    
    processing_msg = await message.reply("📢 Broadcasting to users...")
    total = users_col.count_documents({})
    success = 0
    failed = 0
    
    for user in users_col.find():
        try:
            await message.reply_to_message.copy(user["_id"])
            success += 1
            await asyncio.sleep(0.2)  # Prevent flooding
        except Exception as e:
            failed += 1
            print(f"Failed to send to user {user['_id']}: {str(e)}")
    
    await processing_msg.edit_text(
        f"✅ Broadcast Complete!\n\n"
        f"• Total Users: {total}\n"
        f"• Successfully Sent: {success}\n"
        f"• Failed: {failed}"
    )

@app.on_message(filters.command("grp_broadcast") & filters.user(BOT_OWNER))
async def broadcast_to_groups(client, message: Message):
    if not message.reply_to_message:
        return await message.reply("❌ Please reply to a message to broadcast")
    
    processing_msg = await message.reply("📢 Broadcasting to groups...")
    total = groups_col.count_documents({})
    success = 0
    failed = 0
    
    for group in groups_col.find():
        try:
            await message.reply_to_message.copy(group["_id"])
            success += 1
            await asyncio.sleep(0.5)  # More delay for groups
        except Exception as e:
            failed += 1
            print(f"Failed to send to group {group['_id']}: {str(e)}")
    
    await processing_msg.edit_text(
        f"✅ Group Broadcast Complete!\n\n"
        f"• Total Groups: {total}\n"
        f"• Successfully Sent: {success}\n"
        f"• Failed: {failed}"
    )

@app.on_message(filters.command("chats") & filters.user(BOT_OWNER))
async def list_all_chats(client, message: Message):
    groups = list(groups_col.find())
    if not groups:
        return await message.reply("❌ No groups found in database.")
    
    text = "📋 <b>All Groups</b>:\n\n"
    for group in groups:
        text += f"• <code>{group['_id']}</code> - {group.get('title', 'No Title')}\n"
    
    # Split into multiple messages if too long
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            await message.reply(text[x:x+4000], parse_mode=ParseMode.HTML)
            await asyncio.sleep(1)
    else:
        await message.reply(text, parse_mode=ParseMode.HTML)

@app.on_message(filters.command("users") & filters.user(BOT_OWNER))
async def list_all_users(client, message: Message):
    users = list(users_col.find())
    if not users:
        return await message.reply("❌ No users found in database.")
    
    text = "👥 <b>All Users</b>:\n\n"
    for user in users:
        text += f"• <code>{user['_id']}</code> - {user.get('name', 'No Name')}\n"
    
    # Split into multiple messages if too long
    if len(text) > 4000:
        for x in range(0, len(text), 4000):
            await message.reply(text[x:x+4000], parse_mode=ParseMode.HTML)
            await asyncio.sleep(1)
    else:
        await message.reply(text, parse_mode=ParseMode.HTML)

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
                lang = None

            page = int(page_str)
            normalized_query = normalize_text(query_text)
            query_filter = {
                "normalized_name": {"$regex": normalized_query, "$options": "i"}
            }
            if lang and lang != "All":
                query_filter["language"] = lang.capitalize()

            results = list(files_col.find(query_filter))

            # Remove files that are deleted in DB channel
            filtered_results = []
            for doc in results:
                try:
                    await client.get_messages(doc["chat_id"], doc["message_id"])
                    filtered_results.append(doc)
                except Exception:
                    continue

            if not filtered_results:
                return await query.answer("No files found.", show_alert=True)

            markup = await generate_pagination_buttons(
                filtered_results, (await client.get_me()).username, page, 5,
                prefix, query_text, query.from_user.id, lang or "All", client=client
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
            keyboard = [
                [InlineKeyboardButton("📊 Stats", callback_data="showstats"),
                 InlineKeyboardButton("🗂 Database", callback_data="database")]
            ]
            
            # Add Admin button if user is admin
            if query.from_user.id == BOT_OWNER:
                keyboard.append([InlineKeyboardButton("👑 Admin", callback_data="admin_panel")])
                
            keyboard.append([InlineKeyboardButton("⟲ Back", callback_data="back")])
            
            return await query.message.edit_text(
                "Welcome To My Store!\n\n<blockquote>Note: Under Construction...🚧</blockquote>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )

        # Admin Panel
        elif data == "admin_panel":
            if query.from_user.id != BOT_OWNER:
                return await query.answer("You're not authorized!", show_alert=True)
                
            await query.message.edit_text(
                "👑 <b>Admin Panel</b> 👑\n\n"
                "Available Commands:\n"
                "/broadcast - Broadcast message to all users\n"
                "/grp_broadcast - Broadcast to all groups\n"
                "/chats - List all chats\n"
                "/users - List all users\n"
                "/stats - Show bot stats\n"
                "/logs - View activity logs\n"
                "/clearlogs - Clear all logs\n"
                "/cleanup - Cleanup database",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⟲ Back", callback_data="help")]
                ]),
                parse_mode=ParseMode.HTML
            )
            return await query.answer()

        # Show statistics
        elif data == "showstats":
            users_count = users_col.count_documents({})
            groups_count = groups_col.count_documents({})
            files_count = files_col.count_documents({})
            stats_text = (
                f"<b>- - - - - - 📉 Bot Stats - - - - - -</b>\n"
                f"<b>Total Users:</b> {users_count}\n"
                f"<b>Total Groups:</b> {groups_count}\n"
                f"<b>Total Files:</b> {files_count}\n"
            )
            return await query.message.edit_text(
                stats_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔄 Refresh", callback_data="showstats")],
                    [InlineKeyboardButton("⟲ Back", callback_data="help")]
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

            # Filter out files missing from DB channel
            selected_docs = results[page * per_page: (page + 1) * per_page]
            filtered_docs = []
            for doc in selected_docs:
                try:
                    await client.get_messages(doc["chat_id"], doc["message_id"])
                    filtered_docs.append(doc)
                except Exception:
                    continue

            if not filtered_docs:
                return await query.answer("No files found on this page.", show_alert=True)

            await query.answer("Sending selected files...")
            for doc in filtered_docs:
                try:
                    original_message = await client.get_messages(doc["chat_id"], doc["message_id"])
                    caption = f"<code>{original_message.caption or doc.get('file_name', 'No Caption')}</code>"
                    if original_message.document:
                        await client.send_document(
                            chat_id=query.message.chat.id,
                            document=original_message.document.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    elif original_message.video:
                        await client.send_video(
                            chat_id=query.message.chat.id,
                            video=original_message.video.file_id,
                            caption=caption,
                            parse_mode=ParseMode.HTML
                        )
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Failed to send file: {e}")
            return

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

                # Only keep files that still exist in the channel
                filtered_results = []
                for doc in results:
                    try:
                        await client.get_messages(doc["chat_id"], doc["message_id"])
                        filtered_results.append(doc)
                    except Exception:
                        continue

                if not filtered_results:
                    markup = InlineKeyboardMarkup([[InlineKeyboardButton("⟲ Back", callback_data=f"search:0:{query_text}")]])
                    return await query.message.edit_text(
                        f"Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}.",
                        parse_mode=ParseMode.HTML,
                        reply_markup=markup
                    )

                markup = await generate_pagination_buttons(
                    filtered_results, (await client.get_me()).username, 0, 5, "search", query_text, query.from_user.id, selected_lang, client=client
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
        print(f"Callback data: {data}")
        print(f"Error in callback: {e}")
        await query.answer("An error occurred.", show_alert=True)

async def store_user_channel(channel_id):
    user_channels_col.update_one(
        {"_id": channel_id},
        {"$set": {"_id": channel_id}},
        upsert=True
    )

async def check_and_store_user_channel(client, message: Message):
    if message.forward_from_chat:
        channel_id = message.forward_from_chat.id
        await store_user_channel(channel_id)
        try:
            member = await client.get_chat_member(channel_id, (await client.get_me()).id)
            if member.status not in ("administrator", "creator"):
                print(f"Bot is not an admin in user channel: {channel_id}")
            else:
                print(f"Bot is an admin in user channel: {channel_id}")
        except Exception as e:
            print(f"Error checking admin status for user channel {channel_id}: {e}")

@app.on_message(filters.private & filters.forwarded)
async def process_forwarded_message(client, message: Message):
    # Check and store the user channel
    await check_and_store_user_channel(client, message)

    if not message.forward_from_chat or not message.forward_from_message_id:
        await message.reply_text("❌ Please forward the **last message** from a channel **with quotes**.")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id
    count = 0
    live_message = await message.reply_text("🔍 Scanning files... **0** found")

    # Start from the last message and go backward
    current_msg_id = last_msg_id

    while current_msg_id > 0:
        try:
            msg = await client.get_messages(chat_id, current_msg_id)
            if not msg or not (msg.document or msg.video):
                current_msg_id -= 1
                continue

            media = msg.document or msg.video
            file_name = media.file_name or "Unknown"
            file_size = media.file_size
            file_id = media.file_id
            caption = msg.caption or ""
            combined_text = f"{file_name} {caption}".lower()
            normalized_name = normalize_text(file_name)
            language = extract_language(combined_text)
            file_type = "document" if msg.document else "video"

            # Check for duplicates
            existing = files_col.find_one({
                "file_name": file_name,
                "file_size": file_size
            })
            if existing:
                current_msg_id -= 1
                continue

            # Copy to DB_CHANNEL
            try:
                sent = await client.copy_message(DB_CHANNEL, chat_id, current_msg_id)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue  # Retry after waiting

            files_col.insert_one({
                "file_name": file_name,
                "normalized_name": normalized_name,
                "language": language,
                "file_type": file_type,
                "chat_id": DB_CHANNEL,
                "message_id": sent.id,
                "file_id": sent.document.file_id if sent.document else sent.video.file_id,
                "file_size": file_size
            })

            count += 1
            if count % 5 == 0:  # Update progress every 5 files
                await live_message.edit_text(f"📂 Scanning files... **{count}** found")
            
            current_msg_id -= 1  # Move to the previous message

        except Exception as e:
            print(f"Error at message {current_msg_id}: {e}")
            current_msg_id -= 1  # Skip problematic messages
            continue

    # Final update
    await live_message.edit_text(f"✅ **Done!** {count} files added to the database.")
    
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
            # This is the bot being added to a new group
            existing_group = groups_col.find_one({"_id": message.chat.id})
            if not existing_group:
                await log_event("new_group", message.from_user.id, message.chat.id, {
                    "group_title": message.chat.title,
                    "added_by": message.from_user.id
                })
            
            group_title = message.chat.title
            group_link = f"https://t.me/c/{str(message.chat.id)[4:]}" if str(message.chat.id).startswith("-100") else "https://t.me/"
            caption = (
                f"TʜᴀɴᴋYᴏᴜ! Fᴏʀ Aᴅᴅɪɴɢ Mᴇʜ Tᴏ <a href=\"{group_link}\">{group_title}</a>\n\n"
                f"Lᴇᴛ's Get Started..."
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Sᴜᴘᴘᴏʀᴛ", url=SUPPORT_GROUP), InlineKeyboardButton("Updates", url=UPDATE_CHANNEL)]
            ])
            await message.reply_text(caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    media = message.document or message.video
    file_name = media.file_name or "Unknown"
    file_size = media.file_size
    file_id = media.file_id
    caption = message.caption or ""
    combined_text = f"{file_name} {caption}".lower()
    normalized_name = normalize_text(file_name)
    language = extract_language(combined_text)

    # Check for duplicate by file_name and file_size
    existing = files_col.find_one({
        "file_name": file_name,
        "file_size": file_size
    })
    if existing:
        print(f"Skipped duplicate: {file_name}")
        return

    files_col.insert_one({
        "file_name": file_name,
        "normalized_name": normalized_name,
        "language": language,
        "chat_id": message.chat.id,
        "message_id": message.id,
        "file_id": file_id,
        "file_size": file_size
    })
    print(f"Stored file: {file_name} | Language: {language}")

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    app.run()
