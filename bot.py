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

# Predefined languages
PREDEFINED_LANGUAGES = ["Kannada", "English", "Hindi", "Tamil", "Telugu", "Malayalam"]

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
    
    if start >= len(results):
        page = 0
        start = 0
        end = per_page
        
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
    InlineKeyboardButton("Gᴇᴛ Aʟʟ Fɪʟᴇs", callback_data=f"getfiles:{query}:{page}"),
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
            return await client.copy_message(chat_id=message.chat.id, from_chat_id=doc["chat_id"], message_id=doc["message_id"])
        except Exception as e:
            await emoji_msg.delete()
            return await message.reply(f"❌ Error retrieving file:\n\n{e}")

    bot_username = (await client.get_me()).username
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
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
    normalized_query = normalize_text(query_text)
    results = list(files_col.find({
        "normalized_name": {"$regex": normalized_query, "$options": "i"}
    }))

    if not results:
        return  # Be silent if no results

    markup = generate_pagination_buttons(results, (await client.get_me()).username, 0, 5, "search", query, message.from_user.id)
    await message.reply(
        f"<blockquote>Hello <a href='tg://user?id={message.from_user.id}'>{message.from_user.first_name}</a>👋,</blockquote>\n\nHere is what I found for your search: <code>{message.text.strip()}</code>",
        reply_markup=markup,
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
        
        markup = generate_pagination_buttons(results, (await client.get_me()).username, page, 5, prefix, query_text, query.from_user.id)
        await query.message.edit_reply_markup(markup)
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
    
elif data == "help":
    await query.message.edit_text(
        "Welcome To My Store!\n\n<blockquote>Note: Under Construction...🚧</blockquote>",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("⟲ Back", callback_data="back")]]),
        parse_mode=ParseMode.HTML
    )
elif data == "checksub":
    if await check_subscription(client, query.from_user.id):
        await query.message.edit_text("Joined!")
    else:
        await query.answer("Please join the updates channel to use this bot.", show_alert=True)
    
elif data == "noop":
    await query.answer()

elif data == "back":
    image = random.choice(IMAGE_URLS)
    caption = random.choice(CAPTIONS).format(user_mention=f'<a href="tg://user?id={query.from_user.id}">{query.from_user.first_name}</a>')
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("Add Me To Group", url=f"https://t.me/{(await client.get_me()).username}?startgroup=true")],
        [InlineKeyboardButton("⇋ Help", callback_data="help"), InlineKeyboardButton("About ⇌", callback_data="about")],
        [InlineKeyboardButton("Updates", url=UPDATE_CHANNEL), InlineKeyboardButton("Support", url=SUPPORT_GROUP)]
    ])
    try:
        await query.message.edit_media(InputMediaPhoto(image, caption=caption, parse_mode=ParseMode.HTML), reply_markup=keyboard)
        except:
        await query.message.edit_caption(caption=caption, reply_markup=keyboard, parse_mode=ParseMode.HTML)

if data.startswith("langs:"):
    _, query_text, _ = data.split(":", 2)
    buttons = [
        [InlineKeyboardButton(lang, callback_data=f"langselect:{query_text}:{lang}")]
        for lang in PREDEFINED_LANGUAGES
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
        "file_name": {
            "$regex": f"{query_text}.*\\b{selected_lang}\\b",
            "$options": "i"
        }
    }))
    
    if not results:
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("⟲ Back", callback_data=f"search:0:{query_text}")]
        ])
        
        return await query.message.edit_text(
            f"Nᴏ Fɪʟᴇs Fᴏᴜɴᴅ Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}.",
            parse_mode=ParseMode.HTML,
            reply_markup=markup
        )
        
        markup = generate_pagination_buttons(
            results, (await client.get_me()).username, 0, 5, "search", query_text, query.from_user.id
        )
        await query.message.edit_text(
            f"Fɪʟᴇs Fᴏʀ <code>{query_text}</code> ɪɴ {selected_lang}:", parse_mode=ParseMode.HTML, reply_markup=markup
        )
        return await query.answer()
    
    elif data.startswith("getfiles:"):
        _, query_text, page_str = data.split(":")
        page = int(page_str)
        per_page = 5  # match your pagination limit
        start = page * per_page
        end = start + per_page
            
        results = list(files_col.find({"file_name": {"$regex": query_text, "$options": "i"}}))
        selected_docs = results[start:end]
            
        if not selected_docs:
            return await query.answer("No files found on this page.", show_alert=True)
            await query.answer("Sending selected files...", show_alert=False)
            for doc in selected_docs:
                    
                try:
                    await client.copy_message(
                        chat_id=query.message.chat.id,
                        from_chat_id=doc["chat_id"],
                        message_id=doc["message_id"]
                    )
                    await asyncio.sleep(0.5)
                except FloodWait as e:
                    await asyncio.sleep(e.value)
                except Exception as e:
                    print(f"Failed to send file: {e}")
                continue
        
        elif data == "about":
            bot_username = (await client.get_me()).username
            about_text = f"""- - - - - - 🍿About Me - - - - - -

-ˋˏ✄- - Iᴍ Aɴ <a href='https://t.me/{bot_username}'>Aᴜᴛᴏ Fɪʟᴛᴇʀ Bᴏᴛ</a>
-ˋˏ✄- - Bᴜɪʟᴛ Wɪᴛʜ 💌 <a href='https://www.python.org/'>Pʏᴛʜᴏɴ</a> & <a href='https://docs.pyrogram.org/'>Pʏʀᴏɢʀᴀᴍ</a>
-ˋˏ✄- - Dᴀᴛᴀʙᴀsᴇ : <a href='https://www.mongodb.com/'>MᴏɴɢᴏDB</a>
-ˋˏ✄- - Bᴏᴛ Sᴇʀᴠᴇʀ : <a href='https://Render.com/'>Rᴇɴᴅᴇʀ</a>
"""
            await query.message.edit_text(
                about_text,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("Lord", url="https://t.me/GandhiNote"),
                        InlineKeyboardButton("⟲ Back", callback_data="back")
                    ]
                ]),
                parse_mode=ParseMode.HTML
            )
                
@app.on_message(filters.command("stats"))
async def stats(client, message: Message):
    users = users_col.count_documents({})
    groups = groups_col.count_documents({})
    files = files_col.count_documents({})
    await message.reply(f"""- - - - - - 📉 Bot Stats - - - - - -\n
    Total Users: {users}\n
    Total Groups: {groups}\n
    Total Files: {files}""")

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

import re

def normalize_text(text):
    return re.sub(r'\W+', '', text.lower())  # Remove all non-alphanumeric chars and lowercase

@app.on_message(filters.channel & filters.chat(DB_CHANNEL) & (filters.document | filters.video))
async def save_file(client, message: Message):
    if not message.caption:
        return

    file_name = message.caption.strip()
    normalized_name = normalize_text(file_name)
    file_size = message.document.file_size if message.document else message.video.file_size
    chat_id = message.chat.id
    message_id = message.id

    # Check for duplicates
    duplicate = files_col.find_one({
        "normalized_name": normalized_name,
        "file_size": file_size,
        "chat_id": chat_id
    })

    if duplicate:
        print(f"Duplicate file skipped: {file_name} ({file_size} bytes)")
        return

    # Save new file
    file_doc = {
        "file_name": file_name,
        "normalized_name": normalized_name,
        "file_size": file_size,
        "chat_id": chat_id,
        "message_id": message_id
    }

    files_col.insert_one(file_doc)
    print(f"Stored file: {file_name} ({file_size} bytes)")

@app.on_message(filters.command("storefiles") & filters.user(BOT_OWNER))
async def store_existing_files(client, message: Message):
    await message.reply("Starting to scan channel messages...")

    total = 0
    skipped = 0
    async for msg in client.get_chat_history(DB_CHANNEL, limit=0):
        if not (msg.document or msg.video):
            continue
        if not msg.caption:
            continue

        file_name = msg.caption.strip().lower()
        exists = files_col.find_one({
            "file_name": file_name,
            "chat_id": message.chat.id,
            "message_id": message_id
        })
        if exists:
            skipped += 1
            continue

        files_col.insert_one({
            "file_name": file_name,
            "chat_id": message.chat.id,
            "message_id": message_id,
            "language": "English"  # Set default language or parse if needed
        })
        total += 1

    await message.reply(f"✅ Done.\nStored: {total} new files.\nSkipped (already in DB): {skipped}")

print("starting...")
app.run()
