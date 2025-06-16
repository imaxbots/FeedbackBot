import asyncio
import logging
import os
import random
from dotenv import load_dotenv
from pyrogram import Client, filters, idle, enums
from pyrogram.errors.exceptions.bad_request_400 import ReactionInvalid
from pyrogram.errors.exceptions.flood_420 import FloodWait
from pyrogram.types import Message
from utils.buttons import parse_buttons
from utils.database import get_keyword_response_map
from formats import script
from aiohttp import web

# Configure logging
for handler in logging.root.handlers[:]:
    logging.root.removeHandler(handler)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(os.getenv("LOG_FILE", "bot.log")),
        logging.StreamHandler()
    ]
)

logging.info("🟢 @Feedback")

# Load environment variables
load_dotenv('config.env')
logger = logging.getLogger(__name__)

try:
    logger.info("Loading environment variables")
    API_ID = int(os.getenv("API"))
    API_HASH = os.getenv("HASH")
    BOT_TOKEN = os.getenv("TOKEN")
    LOG_CHANNEL = int(os.getenv("LOG"))
    ADMINS = [int(x) for x in os.getenv("ADMINS", "").split(",") if x.strip().isdigit()]
    FAQ_ENABLED = os.getenv("FAQ", "False").lower() == "true"
    IMG_CLOUD = os.getenv("IMG_CLOUD", "False").lower() == "true"
    PORT = int(os.getenv("PORT", 8080))  # For Koyeb health checks
    logger.info(f"ADMINS loaded: {ADMINS}")
except Exception as e:
    logger.error(f"Error loading environment variables: {e}", exc_info=True)
    raise

# Create a simple web server for health checks
async def health_check(request):
    return web.Response(text="OK")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/healthz', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Health check server started on port {PORT}")

try:
    logger.info("Initializing Pyrogram client")
    app = Client(
        "my_bot",
        api_id=API_ID,
        api_hash=API_HASH,
        bot_token=BOT_TOKEN,
        plugins={"root": "plugs"}
    )
    logger.info("Pyrogram client initialized")
except Exception as e:
    logger.error(f"Error initializing Pyrogram client: {e}", exc_info=True)
    raise

@app.on_message(filters.private & ~filters.command([
    "start", "ping", "alive", "system", "id", "info", "commands", "broadcast",
    "stickerid", "getsticker", "pack", "img", "cup", "cloud", "logs", "send",
    "users", "keyword", "keywords", "clearkeywords", "delkeyword", "save", "listcallbacks", "delcallback", "clearcallbacks", "wiki", "news", 
    "buy", "prodects", "prodect", "sale", "addservice", "editservice", "listservices", "removeservice", "cleanservices", "ocr", "telegraphtxt",
    "telegraph", "getcmds", "help"
]))
async def handle_all_messages(client: Client, message: Message):
    try:
        logger.info(f"Received message from user {message.from_user.id}")
        if message.from_user and message.from_user.is_bot:
            return
        user_text = (message.text or message.caption or "").lower().strip()
        if user_text:
            keyword_map = await get_keyword_response_map()
            for keyword, response in keyword_map.items():
                if keyword in user_text:
                    clean_text, reply_markup = parse_buttons(response)
                    await message.reply_text(
                        clean_text,
                        reply_markup=reply_markup,
                        parse_mode=enums.ParseMode.MARKDOWN
                    )
                    break
            else:
                await message.reply_text(script.REPLY_MSG)
        else:
            await message.reply_text(script.REPLY_MSG)
        await message.forward(LOG_CHANNEL)
        await message.react(random.choice(script.EMOJIS))
    except FloodWait as e:
        logger.error(f"FloodWait: Sleeping for {e.value} seconds")
        await asyncio.sleep(e.value)
        await message.react(random.choice(script.EMOJIS))
    except ReactionInvalid as e:
        logger.error(f"Invalid reaction emoji: {e}")
    except Exception as e:
        logger.error(f"Error in handle_all_messages: {e}", exc_info=True)

@app.on_message(filters.chat(LOG_CHANNEL) & filters.reply & filters.user(ADMINS))
async def handle_admin_reply(client: Client, message: Message):
    try:
        logger.info(f"Received admin reply from user {message.from_user.id}")
        if not message.reply_to_message.forward_origin or not hasattr(message.reply_to_message.forward_origin, 'sender_user'):
            logger.error("No user ID found in forwarded message")
            await message.reply_text("Cannot reply: Original user ID not found.")
            return
        user_id = message.reply_to_message.forward_origin.sender_user.id
        if message.text or message.caption:
            await client.send_message(
                chat_id=user_id,
                text=message.text or message.caption
            )
        if message.photo:
            await client.send_photo(
                chat_id=user_id,
                photo=message.photo.file_id,
                caption=message.caption or ""
            )
        elif message.video:
            await client.send_video(
                chat_id=user_id,
                video=message.video.file_id,
                caption=message.caption or ""
            )
        elif message.document:
            await client.send_document(
                chat_id=user_id,
                document=message.document.file_id,
                caption=message.caption or ""
            )
        elif message.audio:
            await client.send_audio(
                chat_id=user_id,
                audio=message.audio.file_id,
                caption=message.caption or ""
            )
        elif message.sticker:
            await client.send_sticker(
                chat_id=user_id,
                sticker=message.sticker.file_id
            )
        elif message.animation:
            await client.send_animation(
                chat_id=user_id,
                animation=message.animation.file_id,
                caption=message.caption or ""
            )
        logger.info(f"Sent admin reply to user {user_id}")
    except Exception as e:
        logger.error(f"Error in handle_admin_reply: {e}", exc_info=True)
        await message.reply_text(f"Failed to deliver reply to user: {str(e)}")

async def main():
    try:
        logger.info("Starting NX Bot")
        
        # Start the health check server
        await start_web_server()
        
        # Start the Pyrogram client
        await app.start()
        
        # Get bot info to confirm it's running
        me = await app.get_me()
        logger.info(f"Bot Started successfully as @{me.username}")
        
        # Keep the bot running
        await idle()
        
    except Exception as e:
        logger.error(f"Failed to start Bot: {e}", exc_info=True)
        raise
    finally:
        try:
            await app.stop()
            logger.info("Bot Stopped")
        except Exception as e:
            logger.error(f"Error stopping Pyrogram client: {e}", exc_info=True)

if __name__ == "__main__":
    logger.info("Bot is Starting...")
    try:
        # Create event loop and run the main function
        loop = asyncio.get_event_loop()
        loop.run_until_complete(main())
    except Exception as e:
        logger.error(f"Error running bot: {e}", exc_info=True)
        raise
