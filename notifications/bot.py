import os
from aiogram import Bot
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
ADMIN_CHAT_ID = os.getenv("TELEGRAM_ADMIN_CHAT_ID", "123456789")

async def send_telegram_alert(message: str):
    """
    Sends an alert to the configured Telegram chat.
    """
    if BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        print(f"[Telegram Mock] Would send: {message}")
        return
        
    try:
        bot = Bot(token=BOT_TOKEN)
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode="HTML")
        await bot.session.close()
    except Exception as e:
        print(f"Failed to send Telegram alert: {e}")
