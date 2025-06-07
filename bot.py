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
    CallbackQuery, InputMediaPhoto, InlineQueryResultArticle,
    InputTextMessageContent
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

# Deep Link Verification System
async def generate_verify_link(user_id):
    return f"https://t.me/{(await app.get_me()).username}?start=verify_{user_id}"

async def check_verification(user_id):
    if not UPDATE_CHANNEL or user_id == BOT_OWNER:
        return True
    
    try:
        member = await app.get_chat_member(UPDATE_CHANNEL, user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        print(f"Verification error: {e}")
        return False

async def force_sub_required(func):
    async def wrapper(client, message):
        if message.chat.type == "private":
            if len(message.command) > 1 and message.command[1].startswith("verify_"):
                user_id = int(message.command[1].split("_")[1])
                if user_id == message.from_user.id and await check_verification(user_id):
                    return await func(client, message)
            
            if not await check_verification(message.from_user.id):
                verify_link = await generate_verify_link(message.from_user.id)
                await message.reply(
                    "🔒 <b>Access Restricted</b>\n\n"
                    "To use this bot, please:\n"
                    "1. Join our official channel\n"
                    "2. Click the verification button below\n\n"
                    f"Channel: @{UPDATE_CHANNEL}",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("✨ Join Channel", url=f"https://t.me/{UPDATE_CHANNEL}")],
                        [InlineKeyboardButton("🔗 Verify Membership", url=verify_link)],
                        [InlineKeyboardButton("🔄 Try Again", callback_data="checksub")]
                    ]),
                    parse_mode="HTML"
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
    if await check_verification(query.from_user.id):
        await query.answer("✅ Verified! You can now use the bot", show_alert=True)
        await query.message.delete()
        await start_command(client, query.message)
    else:
        verify_link = await generate_verify_link(query.from_user.id)
        await query.answer("❌ Not verified yet", show_alert=True)
        await query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✨ Join Channel", url=f"https://t.me/{UPDATE_CHANNEL}")],
                [InlineKeyboardButton("🔗 Verify Membership", url=verify_link)],
                [InlineKeyboardButton("🔄 Try Again", callback_data="checksub")]
            ])
        )

# [Keep all your existing callback handlers - help_main, about_main, etc]
# [Keep your existing search functionality]
# [Keep your file handling and database operations]

@app.on_inline_query()
async def inline_search(client, inline_query):
    if not await check_verification(inline_query.from_user.id):
        await inline_query.answer(
            results=[],
            switch_pm_text="Join Channel to Use Bot",
            switch_pm_parameter="require_sub"
        )
        return
    
    query = normalize_text(inline_query.query)
    if not query:
        return
    
    results = list(files_col.find({
        "normalized_name": {"$regex": query, "$options": "i"}
    }).limit(50))

    if not results:
        await inline_query.answer(
            results=[],
            switch_pm_text="No results found",
            switch_pm_parameter="no_results"
        )
        return

    answers = []
    for doc in results[:10]:  # Limit to 10 results for inline
        answers.append(
            InlineQueryResultArticle(
                title=doc.get('file_name', 'Unnamed'),
                input_message_content=InputTextMessageContent(
                    f"📁 {doc.get('file_name', 'Unnamed')}\n"
                    f"🔗 https://t.me/{(await app.get_me()).username}?start=file_{doc['_id']}"
                ),
                description=doc.get('caption', '')[:100],
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton(
                        "Get File",
                        url=f"https://t.me/{(await app.get_me()).username}?start=file_{doc['_id']}"
                    )]
                ])
            )
        )
    
    await inline_query.answer(answers, cache_time=1)

print("Bot started with deep link verification!")
app.run()
