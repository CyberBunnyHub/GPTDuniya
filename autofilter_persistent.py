import os
from pyrogram import Client

API_ID = int(os.environ.get("API_ID", 12345))        # Replace with your API_ID or use env vars
API_HASH = os.environ.get("API_HASH", "your_api_hash")
BOT_TOKEN = os.environ.get("BOT_TOKEN", "your_bot_token")

# Make sure the "sessions" directory exists
os.makedirs("sessions", exist_ok=True)

# Use a persistent session file
app = Client("sessions/AutoFilterBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

@app.on_message()
async def echo(_, message):
    await message.reply_text("I'm alive and my session is persistent!")

app.run()