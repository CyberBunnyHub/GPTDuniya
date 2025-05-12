from pyrogram import Client
from bot import config
from bot.handlers import start

app = Client("autofilter_bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# Register handlers
start.register(app)

app.run()
