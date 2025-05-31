import asyncio
import random
import re
import base64
from bson import ObjectId
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.enums import ParseMode
from pyrogram.errors import MessageNotModified, UserNotParticipant, FloodWait, UserIsBlocked
from pyrogram.types import (
    Message, InlineKeyboardMarkup, InlineKeyboardButton,
    CallbackQuery, InputMediaPhoto
)
from flask import Flask
import os
import threading
from datetime import datetime
from config import (
    BOT_TOKEN, API_ID, API_HASH, BOT_OWNER, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, SUPPORT_GROUP, LOG_CHANNEL
)

PREDEFINED_LANGUAGES = ["Kannada", "English", "Hindi", "Tamil", "Telugu", "Malayalam"]

app = Client("CyberBunny", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]
user_channels_col = db["user_channels"]

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

@app.on_message(filters.private & filters.text & ~filters.command(["start", "stats", "help", "about", "cleanup"]) & ~filters.bot)
async def search_and_track(client, message: Message):
    users_col.update_one(
        {"_id": message.from_user.id},
        {"$set": {"name": message.from_user.first_name, "username": message.from_user.username}},
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

@app.on_message(filters.group & filters.text & ~filters.bot)
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
    file_size = media.file_size
    file_id = media.file_id
    caption = message.caption or ""
    combined_text = f"{file_name} {caption}".lower()
    normalized_name = normalize_text(file_name)
    language = extract_language(combined_text)

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

@app.on_message(filters.private & filters.forwarded)
async def process_forwarded_message(client, message: Message):
    if not message.forward_from_chat or not message.forward_from_message_id:
        await message.reply_text("❌ Please forward the last message from a channel with quotes.")
        return

    chat_id = message.forward_from_chat.id
    last_msg_id = message.forward_from_message_id
    count = 0
    live_message = await message.reply_text("🔍 Scanning files... 0 found")

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

            existing = files_col.find_one({
                "file_name": file_name,
                "file_size": file_size
            })
            if existing:
                current_msg_id -= 1
                continue

            try:
                sent = await client.copy_message(DB_CHANNEL, chat_id, current_msg_id)
            except FloodWait as e:
                await asyncio.sleep(e.value)
                continue

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
            if count % 5 == 0:
                await live_message.edit_text(f"📂 Scanning files... {count} found")

            current_msg_id -= 1

        except Exception as e:
            print(f"Error at message {current_msg_id}: {e}")
            current_msg_id -= 1
            continue

    await live_message.edit_text(f"✅ Done! {count} files added to the database.")

@app.on_message(filters.command("cleanup") & filters.user(BOT_OWNER))
async def cleanup_db(client, message: Message):
    await message.reply_text("🔍 Scanning for orphaned (deleted in channel) files, please wait...")
    deleted_count = 0
    for doc in files_col.find({}):
        try:
            await client.get_messages(doc["chat_id"], doc["message_id"])
        except Exception:
            files_col.delete_one({"_id": doc["_id"]})
            deleted_count += 1
    await message.reply_text(f"✅ Cleanup complete. Deleted {deleted_count} orphaned file entries.")

@app.on_message(filters.command("broadcast") & filters.user(BOT_OWNER))
async def broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Please reply to a message to broadcast.")
        return

    users = users_col.find({})
    total = users_col.count_documents({})
    success = 0
    failed = 0
    blocked = 0
    processing_msg = await message.reply_text(f"📤 Broadcast started...\nTotal users: {total}\nSuccess: {success}\nFailed: {failed}\nBlocked: {blocked}")

    start_time = datetime.now()

    for user in users:
        try:
            await message.reply_to_message.copy(user["_id"])
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except UserIsBlocked:
            blocked += 1
            continue
        except Exception as e:
            failed += 1
            continue

        if (success + failed + blocked) % 10 == 0:
            try:
                await processing_msg.edit_text(
                    f"📤 Broadcasting...\n"
                    f"Total users: {total}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}\n"
                    f"Blocked: {blocked}\n"
                    f"Progress: {((success + failed + blocked)/total)*100:.1f}%"
                )
            except Exception:
                pass
        await asyncio.sleep(0.1)

    time_taken = (datetime.now() - start_time).seconds
    await processing_msg.edit_text(
        f"✅ Broadcast completed!\n\n"
        f"• Total users: {total}\n"
        f"• Success: {success}\n"
        f"• Failed: {failed}\n"
        f"• Blocked: {blocked}\n"
        f"• Time taken: {time_taken} seconds\n\n"
        f"Success rate: {(success/total)*100:.1f}%"
    )

@app.on_message(filters.command("grp_broadcast") & filters.user(BOT_OWNER))
async def group_broadcast_cmd(client, message: Message):
    if not message.reply_to_message:
        await message.reply_text("Please reply to a message to broadcast to groups.")
        return

    groups = groups_col.find({})
    total = groups_col.count_documents({})
    success = 0
    failed = 0
    processing_msg = await message.reply_text(f"📢 Group broadcast started...\nTotal groups: {total}\nSuccess: {success}\nFailed: {failed}")

    start_time = datetime.now()

    for group in groups:
        try:
            await message.reply_to_message.copy(group["_id"])
            success += 1
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            failed += 1
            continue

        if (success + failed) % 5 == 0:
            try:
                await processing_msg.edit_text(
                    f"📢 Broadcasting to groups...\n"
                    f"Total groups: {total}\n"
                    f"Success: {success}\n"
                    f"Failed: {failed}\n"
                    f"Progress: {((success + failed)/total)*100:.1f}%"
                )
            except Exception:
                pass
        await asyncio.sleep(0.5)

    time_taken = (datetime.now() - start_time).seconds
    await processing_msg.edit_text(
        f"✅ Group broadcast completed!\n\n"
        f"• Total groups: {total}\n"
        f"• Success: {success}\n"
        f"• Failed: {failed}\n"
        f"• Time taken: {time_taken} seconds\n\n"
        f"Success rate: {(success/total)*100:.1f}%"
    )

USERS_PER_PAGE = 10
CHATS_PER_PAGE = 10

@app.on_message(filters.command("user") & filters.user(BOT_OWNER))
async def user_list_cmd(client, message: Message):
    args = message.text.split()
    page = 0
    if len(args) > 1 and args[1].isdigit():
        page = int(args[1])
    skip = page * USERS_PER_PAGE
    users = list(users_col.find().sort("_id", -1).skip(skip).limit(USERS_PER_PAGE))
    total = users_col.count_documents({})
    if not users:
        return await message.reply_text("No users found.")

    text = "<b>📊 Bot Users</b>\n\n"
    for i, user in enumerate(users, start=skip + 1):
        name = user.get('name', 'Unknown')
        tguser = (f" (@{user.get('username')})" if user.get('username') else "")
        text += f"{i}. <code>{user['_id']}</code> - {name}{tguser}\n"
    text += f"\nTotal Users: {total}"

    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"userlist:{page-1}"))
    nav_row.append(InlineKeyboardButton(f"Page {page+1}/{(total-1)//USERS_PER_PAGE+1}", callback_data="noop"))
    if skip + USERS_PER_PAGE < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"userlist:{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])

    await message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
    )

@app.on_message(filters.command("chat") & filters.user(BOT_OWNER))
async def chat_list_cmd(client, message: Message):
    args = message.text.split()
    page = 0
    if len(args) > 1 and args[1].isdigit():
        page = int(args[1])
    skip = page * CHATS_PER_PAGE
    chats = list(groups_col.find().sort("_id", -1).skip(skip).limit(CHATS_PER_PAGE))
    total = groups_col.count_documents({})
    if not chats:
        return await message.reply_text("No chats found.")

    text = "<b>💬 Bot Chats</b>\n\n"
    for i, chat in enumerate(chats, start=skip + 1):
        title = chat.get('title', 'Unknown')
        text += f"{i}. <code>{chat['_id']}</code> - {title}\n"
    text += f"\nTotal Chats: {total}"

    buttons = []
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"chatlist:{page-1}"))
    nav_row.append(InlineKeyboardButton(f"Page {page+1}/{(total-1)//CHATS_PER_PAGE+1}", callback_data="noop"))
    if skip + CHATS_PER_PAGE < total:
        nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"chatlist:{page+1}"))
    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])

    await message.reply_text(
        text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
    )

@app.on_callback_query()
async def unified_callback_handler(client, query: CallbackQuery):
    data = query.data
    try:
        # Userlist pagination
        if data.startswith("userlist:"):
            page = int(data.split(":")[1])
            skip = page * USERS_PER_PAGE
            users = list(users_col.find().sort("_id", -1).skip(skip).limit(USERS_PER_PAGE))
            total = users_col.count_documents({})
            text = "<b>📊 Bot Users</b>\n\n"
            for i, user in enumerate(users, start=skip + 1):
                name = user.get('name', 'Unknown')
                tguser = (f" (@{user.get('username')})" if user.get('username') else "")
                text += f"{i}. <code>{user['_id']}</code> - {name}{tguser}\n"
            text += f"\nTotal Users: {total}"
            buttons = []
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"userlist:{page-1}"))
            nav_row.append(InlineKeyboardButton(f"Page {page+1}/{(total-1)//USERS_PER_PAGE+1}", callback_data="noop"))
            if skip + USERS_PER_PAGE < total:
                nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"userlist:{page+1}"))
            if nav_row:
                buttons.append(nav_row)
            buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
            await query.message.edit_text(
                text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
            )
            return await query.answer()

        # Chatlist pagination
        elif data.startswith("chatlist:"):
            page = int(data.split(":")[1])
            skip = page * CHATS_PER_PAGE
            chats = list(groups_col.find().sort("_id", -1).skip(skip).limit(CHATS_PER_PAGE))
            total = groups_col.count_documents({})
            text = "<b>💬 Bot Chats</b>\n\n"
            for i, chat in enumerate(chats, start=skip + 1):
                title = chat.get('title', 'Unknown')
                text += f"{i}. <code>{chat['_id']}</code> - {title}\n"
            text += f"\nTotal Chats: {total}"
            buttons = []
            nav_row = []
            if page > 0:
                nav_row.append(InlineKeyboardButton("⬅️ Prev", callback_data=f"chatlist:{page-1}"))
            nav_row.append(InlineKeyboardButton(f"Page {page+1}/{(total-1)//CHATS_PER_PAGE+1}", callback_data="noop"))
            if skip + CHATS_PER_PAGE < total:
                nav_row.append(InlineKeyboardButton("Next ➡️", callback_data=f"chatlist:{page+1}"))
            if nav_row:
                buttons.append(nav_row)
            buttons.append([InlineKeyboardButton("❌ Close", callback_data="close_msg")])
            await query.message.edit_text(
                text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML
            )
            return await query.answer()

        # Close message
        elif data == "close_msg":
            await query.message.delete()
            return await query.answer()

        # Check subscription
        elif data == "checksub":
            if await check_subscription(client, query.from_user.id):
                await query.answer("You have joined! Try again.", show_alert=True)
            else:
                await query.answer("You need to join the channel!", show_alert=True)
            return

        # Noop (for page info)
        elif data == "noop":
            return await query.answer()

        # Add other callbacks as needed (help, about, deletefile, etc.)
        # Example for deleting a file
        elif data.startswith("deletefile:") and query.from_user.id == BOT_OWNER:
            file_id = data.split(":")[1]
            doc = files_col.find_one({"_id": ObjectId(file_id)})
            if not doc:
                await query.answer("File not found.", show_alert=True)
                return
            try:
                # Delete message from the channel
                await client.delete_messages(doc["chat_id"], doc["message_id"])
            except Exception:
                pass
            files_col.delete_one({"_id": doc["_id"]})
            await query.answer("File deleted!", show_alert=True)
            await query.message.edit_text("File deleted from database and channel.")

        # Add help/about callback handling as you want

    except Exception as e:
        print(f"Callback data: {data}")
        print(f"Error in callback: {e}")
        await query.answer("An error occurred.", show_alert=True)

async def periodic_cleanup():
    while True:
        try:
            print("Running periodic cleanup...")
            deleted_count = 0
            for doc in files_col.find({}):
                try:
                    await app.get_messages(doc["chat_id"], doc["message_id"])
                except Exception:
                    files_col.delete_one({"_id": doc["_id"]})
                    deleted_count += 1
            print(f"Cleanup complete. Deleted {deleted_count} orphaned files.")
        except Exception as e:
            print(f"Error during cleanup: {e}")
        await asyncio.sleep(3600)

if __name__ == "__main__":
    threading.Thread(target=run_flask).start()
    loop = asyncio.get_event_loop()
    loop.create_task(periodic_cleanup())
    app.run()
