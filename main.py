
import os
from pyrogram import Client, filters
from pymongo import MongoClient

API_ID = int(os.environ.get("API_ID", 14853951))  # Replace or set as env var
API_HASH = os.environ.get("API_HASH", "0a33bc287078d4dace12aaecc8e73545")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7845318227:AAFIWjneKzVu_MmAsNDkD3B6NvXzlbMdCgU")
MONGO_URI = os.environ.get("MONGO_URI", "mongodb+srv://CyberBunny:Bunny2008@cyberbunny.5yyorwj.mongodb.net/?retryWrites=true&w=majority")
FILES_CHANNEL = int(os.environ.get("FILES_CHANNEL",  -1002511163521))  # Channel with files

# Set up MongoDB
mongo = MongoClient(MONGO_URI)
db = mongo["CBI"]
files_col = db["files"]

app = Client("movie-filter-bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# Index new files from the channel
@app.on_message(filters.channel & (filters.document | filters.video | filters.audio) & filters.chat(FILES_CHANNEL))
async def index_files(client, message):
    file_name = message.document.file_name if message.document else message.video.file_name if message.video else message.audio.file_name
    file_id = message.document.file_id if message.document else message.video.file_id if message.video else message.audio.file_id
    files_col.update_one(
        {"file_id": file_id},
        {"$set": {
            "file_id": file_id,
            "file_name": file_name,
            "message_id": message.message_id
        }},
        upsert=True
    )

# Search handler
@app.on_message(filters.private & filters.text & ~filters.command("start"))
async def search_movie(client, message):
    user_query = message.text.strip()
    results = list(files_col.find({"file_name": {"$regex": user_query, "$options": "i"}}).limit(10))
    if not results:
        await message.reply("No results found. Try another name.")
        return
    reply_text = "Here are the files I found:\n\n"
    for file in results:
        reply_text += f"[{file['file_name']}](https://t.me/c/{str(FILES_CHANNEL)[4:]}/{file['message_id']})\n"
    await message.reply(reply_text, disable_web_page_preview=True)

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply("Hello! Send me a movie name to search.")

if __name__ == "__main__":
    app.run()
