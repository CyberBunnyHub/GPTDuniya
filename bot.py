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

def normalize_text(text):
    return re.sub(r"[^\w\s]", " ", text).lower().strip()

async def verify_subscription(user_id):
    if not UPDATE_CHANNEL or user_id == BOT_OWNER:
        return True
        
    try:
        member = await app.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except UserNotParticipant:
        return False
    except Exception as e:
        print(f"Subscription error: {e}")
        return True

async def force_sub_required(func):
    async def wrapper(client, message):
        if message.chat.type == "private" and not await verify_subscription(message.from_user.id):
            try:
                invite_link = await app.export_chat_invite_link(UPDATE_CHANNEL)
            except:
                invite_link = UPDATE
                
            await message.reply(
                f"**⚠️ Subscription Required**\n\n"
                f"Please join our channel to use this bot:\n"
                f"➠ [Click Here]({invite_link})\n\n"
                "After joining, send /start again",
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("✨ Join Channel", url=invite_link)],
                    [InlineKeyboardButton("🔄 I've Joined", callback_data="checksub")]
                ])
            )
            return
        return await func(client, message)
    return wrapper

@app.on_message(filters.command("start") & filters.private)
@force_sub_required
async def start_command(client, message):
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS).format(
        user_mention=f'<a href="tg://user?id={message.from_user.id}">{message.from_user.first_name}</a>'
    )
    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help_main"),
            InlineKeyboardButton("📚 About", callback_data="about_main")
        ],
        [
            InlineKeyboardButton("📢 Updates", url=UPDATE),
            InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)
        ]
    ])

    await message.reply_photo(
        photo=image,
        caption=caption,
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^checksub$"))
async def check_sub_callback(client, query):
    if await verify_subscription(query.from_user.id):
        await query.answer("✅ Verified! You can now use the bot", show_alert=True)
        await query.message.delete()
        await start_command(client, query.message)
    else:
        await query.answer("❌ You haven't joined the channel yet", show_alert=True)

@app.on_callback_query(filters.regex("^help_main$"))
async def help_command(client, query):
    help_text = """
<b>📚 Help Guide</b>

🔍 <b>How to Search:</b>
Simply type the movie/series name you're looking for

🎬 <b>How to Get Files:</b>
1. Use the search results
2. Click on the file you want
3. Wait for the file to be sent

📌 <b>Note:</b>
• Use correct spelling for better results
• Join our channel for regular updates
"""
    await query.message.edit_caption(
        caption=help_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")],
            [InlineKeyboardButton("📊 Stats", callback_data="bot_stats")]
        ]),
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^about_main$"))
async def about_command(client, query):
    about_text = f"""
<b>🤖 About This Bot</b>

This is an advanced auto-filter bot that can search through thousands of files in seconds.

<b>🛠️ Technical Details:</b>
• Powered by Pyrogram
• MongoDB Database
• Fast and efficient searching
• Multi-language support
"""
    await query.message.edit_caption(
        caption=about_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_start")],
            [InlineKeyboardButton("👨‍💻 Developer", url="https://t.me/GandhiNote")]
        ]),
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^bot_stats$"))
async def stats_command(client, query):
    users_count = users_col.count_documents({})
    files_count = files_col.count_documents({})
    groups_count = groups_col.count_documents({})
    
    stats_text = f"""
<b>📊 Bot Statistics</b>

👤 Users: <code>{users_count}</code>
🗂 Files: <code>{files_count}</code>
👥 Groups: <code>{groups_count}</code>
"""
    await query.message.edit_caption(
        caption=stats_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="help_main")]
        ]),
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^back_to_start$"))
async def back_to_start(client, query):
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS).format(
        user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>'
    )
    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Add Me To Group", url=f"https://t.me/{bot_username}?startgroup=true")],
        [
            InlineKeyboardButton("ℹ️ Help", callback_data="help_main"),
            InlineKeyboardButton("📚 About", callback_data="about_main")
        ],
        [
            InlineKeyboardButton("📢 Updates", url=UPDATE),
            InlineKeyboardButton("💬 Support", url=SUPPORT_GROUP)
        ]
    ])
    
    try:
        await query.message.edit_media(
            InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML),
            reply_markup=keyboard
        )
    except:
        await query.message.edit_caption(
            caption=caption,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML
        )

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help", "about"]))
@force_sub_required
async def search_files(client, message):
    query = normalize_text(message.text.strip())
    results = list(files_col.find({
        "normalized_name": {"$regex": query, "$options": "i"}
    }).limit(50))

    if not results:
        await message.reply("No results found for your query.")
        return

    bot_username = (await client.get_me()).username
    buttons = []
    for doc in results[:10]:  # Show first 10 results
        file_name = doc.get('file_name', 'Unnamed')[:30]
        buttons.append([
            InlineKeyboardButton(
                f"🎬 {file_name}",
                url=f"https://t.me/{bot_username}?start=file_{doc['_id']}"
            )
        ])
    
    # Add navigation buttons if more than 10 results
    if len(results) > 10:
        buttons.append([
            InlineKeyboardButton("⬅️ Previous", callback_data="prev_page"),
            InlineKeyboardButton("➡️ Next", callback_data="next_page")
        ])
    
    buttons.append([InlineKeyboardButton("🔙 Main Menu", callback_data="back_to_start")])
    
    await message.reply(
        f"🔍 Results for: <code>{message.text.strip()}</code>\n\n"
        f"📄 Found {len(results)} files",
        reply_markup=InlineKeyboardMarkup(buttons),
        parse_mode=ParseMode.HTML
    )

@app.on_callback_query(filters.regex("^file_"))
async def send_requested_file(client, query):
    file_id = query.data.split("_")[1]
    file_data = files_col.find_one({"_id": ObjectId(file_id)})
    
    if not file_data:
        await query.answer("File not found", show_alert=True)
        return
    
    try:
        await client.copy_message(
            chat_id=query.from_user.id,
            from_chat_id=file_data["chat_id"],
            message_id=file_data["message_id"]
        )
        await query.answer("File sent to your PM", show_alert=True)
    except Exception as e:
        print(f"Error sending file: {e}")
        await query.answer("Failed to send file", show_alert=True)

print("Bot is running...")
app.run()
