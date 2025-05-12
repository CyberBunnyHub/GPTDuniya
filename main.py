import logging
from pyrogram import Client, filters
from config import Config
from pymongo import MongoClient

# Enable logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MongoDB connection
mongo_client = MongoClient(Config.MONGO_URL)
db = mongo_client["autofilterbot"]
filters_collection = db["filters"]

# Pyrogram client
app = Client(
    "autofilterbot",
    api_id=Config.API_ID,
    api_hash=Config.API_HASH,
    bot_token=Config.BOT_TOKEN
)

# /start command
@app.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    await message.reply_text("Hello! I'm an admin-only auto filter bot.")

# Admin-only filter adding
@app.on_message(filters.command("addfilter") & filters.private)
async def add_filter(client, message):
    if message.from_user.id not in Config.ADMINS:
        return await message.reply_text("You are not authorized to use this command.")

    try:
        _, keyword, reply = message.text.split(" ", 2)
    except ValueError:
        return await message.reply_text("Usage: /addfilter <keyword> <reply_text>")

    filters_collection.update_one(
        {"keyword": keyword},
        {"$set": {"reply": reply}},
        upsert=True
    )
    await message.reply_text(f"Filter '{keyword}' added.")

# Admin-only filter deletion
@app.on_message(filters.command("delfilter") & filters.private)
async def delete_filter(client, message):
    if message.from_user.id not in Config.ADMINS:
        return await message.reply_text("You are not authorized to use this command.")

    try:
        _, keyword = message.text.split(" ", 1)
    except ValueError:
        return await message.reply_text("Usage: /delfilter <keyword>")

    result = filters_collection.delete_one({"keyword": keyword})
    if result.deleted_count:
        await message.reply_text(f"Filter '{keyword}' deleted.")
    else:
        await message.reply_text("No such filter found.")

# Message handler to reply if keyword is found
@app.on_message(filters.text & filters.private)
async def keyword_reply(client, message):
    keyword = message.text.strip().lower()
    result = filters_collection.find_one({"keyword": keyword})
    if result:
        await message.reply_text(result["reply"])

# Notify log channel on startup
@app.on_message(filters.command("ping") & filters.user(Config.ADMINS))
async def ping_handler(client, message):
    await message.reply_text("Pong!")

@app.on_message(filters.command("log") & filters.user(Config.ADMINS))
async def log_startup(client, message):
    await client.send_message(Config.LOG_CHANNEL, "Bot started and ready.")

# Start the bot
if __name__ == "__main__":
    logger.info("Bot starting...")
    app.run()
