import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Client("ForceSubBot", 
             api_id=API_ID, 
             api_hash=API_HASH, 
             bot_token=BOT_TOKEN,
             workers=100)

class VerificationSystem:
    def __init__(self):
        self.verified_users = set()
    
    async def is_verified(self, user_id):
        if user_id in self.verified_users:
            return True
        
        try:
            member = await app.get_chat_member(UPDATE_CHANNEL, user_id)
            if member.status in ["member", "administrator", "creator"]:
                self.verified_users.add(user_id)
                return True
        except Exception as e:
            logger.error(f"Verification error for {user_id}: {e}")
        return False

verification = VerificationSystem()

@app.on_message(filters.private & filters.command("start"))
async def start_handler(client, message):
    try:
        if not await verification.is_verified(message.from_user.id):
            verify_url = f"https://t.me/{(await app.get_me()).username}?start=verify_{message.from_user.id}"
            
            await message.reply(
                "🔒 Please verify your subscription:\n\n"
                "1. Join our channel\n"
                "2. Click Verify button\n\n"
                f"Channel: @{UPDATE_CHANNEL}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("Join Channel", url=f"https://t.me/{UPDATE_CHANNEL}")],
                    [InlineKeyboardButton("Verify Now", url=verify_url)]
                ])
            )
            return
            
        await message.reply(
            "✅ Verified! Bot features unlocked.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("Search Files", switch_inline_query_current_chat="")]
            ])
        )
        
    except Exception as e:
        logger.error(f"Start handler error: {e}")
        await message.reply("⚠️ An error occurred. Please try again.")

@app.on_message(filters.private & filters.regex(r'^verify_\d+$'))
async def verify_handler(client, message):
    try:
        user_id = int(message.text.split('_')[1])
        if await verification.is_verified(user_id):
            await message.reply("✅ Verification successful!")
        else:
            await message.reply("❌ Please join the channel first!")
    except Exception as e:
        logger.error(f"Verify handler error: {e}")
        await message.reply("⚠️ Verification failed. Try again.")

async def run_bot():
    await app.start()
    logger.info("Bot started successfully")
    await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        logger.info("Bot stopped")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
