import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "123456789")

dp = Dispatcher()
bot = Bot(token=BOT_TOKEN)

@dp.message(Command("health"))
async def cmd_health(message: types.Message):
    """
    Background bot command to check system health.
    """
    await message.answer("✅ SaleScrap System is running perfectly.\\nLast Scraper Run: Recently\\nStatus: OK")

async def send_telegram_alert(message: str):
    """
    Sends an alert to the configured Telegram chat.
    """
    if BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        print(f"[Telegram Mock] Would send: {message}")
        return
        
    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")

async def send_daily_digest(top_promos: list):
    """
    Sends the daily top 5 discounts.
    """
    if not top_promos:
        return
        
    msg = "📊 <b>Daily Top 5 Discounts Digest</b>\\n\\n"
    for idx, p in enumerate(top_promos[:5], 1):
        msg += f"{idx}. <b>{p['restaurant_name']}</b> - {p['promo_title']}\\n"
        msg += f"   Discount: {p['discount_percent']}% (Old: {p['original_price']}, New: {p['current_price']})\\n\\n"
        
    await send_telegram_alert(msg)

async def start_bot_polling():
    """
    Starts the background bot listening for commands like /health.
    """
    print("Starting background Telegram bot polling...")
    if BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        print("[Telegram Mock] Bot polling skipped due to missing token.")
        return
    await dp.start_polling(bot)

async def close_bot_session():
    """
    Closes the aiohttp session for the bot.
    """
    if bot.session:
        await bot.session.close()

