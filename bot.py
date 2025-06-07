import asyncio
import random
import re
import base64
from datetime import datetime, timedelta
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
from multiprocessing import Process

from config import (
    BOT_TOKEN, LOG_CHANNEL, API_ID, API_HASH, BOT_OWNER, MONGO_URI,
    DB_CHANNEL, IMAGE_URLS, CAPTIONS,
    UPDATE_CHANNEL, UPDATE, SUPPORT_GROUP
)

PREDEFINED_LANGUAGES = ["Kannada", "English", "Hindi", "Tamil", "Telugu", "Malayalam"]

app = Client("CyberBunny", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
mongo = MongoClient(MONGO_URI)
db = mongo["autofilter"]
files_col = db["files"]
users_col = db["users"]
groups_col = db["groups"]

flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    flask_app.run(host="0.0.0.0", port=port)

def normalize_text(text):
    return re.sub(r"[^\w\s]", " ", text).lower().strip()

async def check_user_subscribed(client, user_id):
    if not UPDATE_CHANNEL:
        return True
    
    try:
        if UPDATE_CHANNEL.startswith("@"):
            channel = UPDATE_CHANNEL
        else:
            channel = int(UPDATE_CHANNEL) if UPDATE_CHANNEL.lstrip("-").isdigit() else UPDATE_CHANNEL
        
        member = await client.get_chat_member(channel, user_id)
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except Exception as e:
        print(f"Subscription check error: {e}")
        return True

async def force_sub_handler(client, message):
    if message.from_user and message.from_user.id == BOT_OWNER:
        return True
        
    if message.chat.type != "private":
        return True
        
    is_subscribed = await check_user_subscribed(client, message.from_user.id)
    if not is_subscribed:
        try:
            if str(UPDATE_CHANNEL).startswith("-100"):
                channel_link = f"https://t.me/c/{str(UPDATE_CHANNEL)[4:]}"
            elif str(UPDATE_CHANNEL).startswith("@"):
                channel_link = f"https://t.me/{UPDATE_CHANNEL[1:]}"
            else:
                channel_link = f"https://t.me/{UPDATE_CHANNEL}"
                
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("✨ Join Channel", url=channel_link)],
                [InlineKeyboardButton("🔄 Check Again", callback_data="check_sub")],
                [InlineKeyboardButton("❌ Close", callback_data="close_sub")]
            ])
            
            await message.reply(
                f"**⚠️ Access Restricted!**\n\n"
                f"To use this bot, please join our channel first:\n"
                f"➠ @{UPDATE_CHANNEL if UPDATE_CHANNEL.startswith('@') else UPDATE_CHANNEL}\n\n"
                "After joining, click 'Check Again' below",
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
            return False
        except Exception as e:
            print(f"Force sub error: {e}")
            return True
            
    return True

async def cleanup_old_messages():
    while True:
        try:
            threshold = datetime.now() - timedelta(hours=6)
            users = users_col.find({"last_force_sub_msg": {"$exists": True}})
            
            for user in users:
                if user.get("last_sub_check", datetime.min) < threshold:
                    try:
                        await app.delete_messages(user["_id"], user["last_force_sub_msg"])
                        await users_col.update_one(
                            {"_id": user["_id"]},
                            {"$unset": {"last_force_sub_msg": ""}}
                        )
                    except Exception:
                        continue
                    
        except Exception as e:
            print(f"Cleanup error: {e}")
            
        await asyncio.sleep(3600)

@app.on_message(filters.command("start") & filters.private)
async def start_handler(client, message):
    if not await force_sub_handler(client, message):
        return
        
    loading = await message.reply("🍿")
    await asyncio.sleep(1)
    await loading.delete()

    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS).format(
        user_mention=f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    )
    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
        [InlineKeyboardButton("Updates", url=UPDATE), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
    ])

    await message.reply_photo(
        photo=image,
        caption=caption,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^check_sub$"))
async def check_sub_callback(client, query: CallbackQuery):
    is_subscribed = await check_user_subscribed(client, query.from_user.id)
    if is_subscribed:
        await query.answer("Thanks for joining! ✅", show_alert=True)
        await query.message.delete()
        await start_handler(client, query.message)
    else:
        await query.answer("You haven't joined the channel yet.", show_alert=True)

@app.on_callback_query(filters.regex("^close_sub$"))
async def close_sub_callback(client, query: CallbackQuery):
    await query.message.delete()

@app.on_message(filters.text & ~filters.command(["start", "stats", "help", "about"]) & ~filters.bot)
async def search_handler(client, message: Message):
    if not await force_sub_handler(client, message):
        return
        
    if message.chat.type == "private":
        users_col.update_one(
            {"_id": message.from_user.id},
            {"$set": {"name": message.from_user.first_name, "last_active": datetime.now()}},
            upsert=True
        )
    else:
        groups_col.update_one(
            {"_id": message.chat.id},
            {"$set": {"title": message.chat.title, "last_active": datetime.now()}},
            upsert=True
        )

    query = normalize_text(message.text.strip())
    results = list(files_col.find({
        "normalized_name": {"$regex": query, "$options": "i"}
    }))

    if not results:
        if message.chat.type == "private":
            await message.reply("No results found for your query.")
        return

    markup = await generate_pagination_buttons(
        results, 
        (await client.get_me()).username, 
        0, 
        5, 
        "search", 
        query, 
        message.from_user.id if message.chat.type == 'private' else None
    )
    
    reply_text = f"<blockquote>Hello {message.from_user.mention() if message.chat.type == 'private' else message.chat.title}👋,</blockquote>\n\nResults for: <code>{message.text.strip()}</code>"
    
    if message.chat.type == "private":
        await message.reply(reply_text, reply_markup=markup, parse_mode=ParseMode.HTML)
    else:
        await message.reply(
            reply_text,
            reply_markup=markup,
            parse_mode=ParseMode.HTML,
            reply_to_message_id=message.id
        )

@app.on_callback_query()
async def callback_handler(client, query: CallbackQuery):
    data = query.data
    
    try:
        if data.startswith("search:"):
            parts = data.split(":")
            page = int(parts[1])
            search_query = parts[2] if len(parts) > 2 else ""
            lang = parts[3] if len(parts) > 3 else "All"

            query_filter = {
                "normalized_name": {"$regex": normalize_text(search_query), "$options": "i"}
            }
            if lang != "All":
                query_filter["language"] = lang

            results = list(files_col.find(query_filter))
            valid_results = [doc for doc in results if await verify_file_exists(client, doc)]

            if not valid_results:
                return await query.answer("No files found.", show_alert=True)

            markup = await generate_pagination_buttons(
                valid_results, 
                (await client.get_me()).username, 
                page, 
                5, 
                "search", 
                search_query, 
                query.from_user.id,
                lang
            )

            try:
                await query.message.edit_reply_markup(markup)
            except MessageNotModified:
                pass
            return await query.answer()

        elif data == "help":
            keyboard = [
                [InlineKeyboardButton("📊 Stats", callback_data="showstats"),
                 InlineKeyboardButton("🗂 Database", callback_data="database")],
                [InlineKeyboardButton("⟲ Back", callback_data="back")]
            ]
            
            if query.from_user.id == BOT_OWNER:
                keyboard.insert(1, [InlineKeyboardButton("👑 Admin", callback_data="admin_panel")])
                
            await query.message.edit_text(
                "Welcome To My Store!\n\n<blockquote>{Note: Under Construction...🚧}</blockquote>",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.HTML
            )

        elif data == "back":
            image = random.choice(IMAGE_URLS)
            caption = random.choice(CAPTIONS).format(
                user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>'
            )
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
                [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
                [InlineKeyboardButton("Updates", url=UPDATE), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
            ])
            try:
                await query.message.edit_media(InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML), reply_markup=keyboard)
            except Exception:
                await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

        elif data.startswith("langs:"):
            _, query_text, _ = data.split(":", 2)
            encoded_query = base64.urlsafe_b64encode(query_text.encode()).decode()
            buttons = [[InlineKeyboardButton(lang, callback_data=f"langselect:{encoded_query}:{lang}")]
                       for lang in PREDEFINED_LANGUAGES]
            buttons.append([InlineKeyboardButton("⟲ Back", callback_data=f"search:0:{query_text}")])
            await query.message.edit_text(
                f"Sᴇʟᴇᴄᴛ Lᴀɴɢᴜᴀɢᴇ Fᴏʀ: <code>{query_text}</code>",
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode=ParseMode.HTML
            )

        elif data.startswith("langselect:"):
            _, encoded_query, selected_lang = data.split(":", 2)
            query_text = base64.urlsafe_b64decode(encoded_query.encode()).decode()
            selected_lang = selected_lang.capitalize()

            results = list(files_col.find({
                "normalized_name": {"$regex": normalize_text(query_text), "$options": "i"},
                "language": selected_lang
            }))
            valid_results = [doc for doc in results if await verify_file_exists(client, doc)]

            if not valid_results:
                markup = InlineKeyboardMarkup([[InlineKeyboardButton("⟲ Back", callback_data=f"search:0:{query_text}")]])
                return await query.message.edit_text(
                    f"Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=markup
                )

            markup = await generate_pagination_buttons(
                valid_results, 
                (await client.get_me()).username, 
                0, 
                5, 
                "search", 
                query_text, 
                query.from_user.id,
                selected_lang
            )
            await query.message.edit_text(
                f"Fɪʟᴇs Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}:",
                parse_mode=ParseMode.HTML,
                reply_markup=markup
            )

        await query.answer()
    except Exception as e:
        print(f"Callback error: {e}")
        await query.answer("An error occurred.", show_alert=True)

def start_bot():
    app.run()

if __name__ == "__main__":
    flask_process = Process(target=run_flask)
    flask_process.start()
    
    # Start the cleanup task in a separate thread
    import threading
    cleanup_thread = threading.Thread(target=asyncio.run, args=(cleanup_old_messages(),))
    cleanup_thread.daemon = True
    cleanup_thread.start()
    
    start_bot()
    
    flask_process.terminate()
