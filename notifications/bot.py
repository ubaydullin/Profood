import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from database.db import AsyncSessionLocal
from database.models import PriceSnapshot
from sqlalchemy import select, func

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
    try:
        async with AsyncSessionLocal() as db:
            stmt = select(func.max(PriceSnapshot.snapshot_at))
            result = await db.execute(stmt)
            latest_run = result.scalar()

            if latest_run:
                await message.answer(
                    f"✅ Система SaleScrap работает.\nПоследний сбор данных: {latest_run.strftime('%Y-%m-%d %H:%M:%S')}\nСтатус: OK"
                )
            else:
                await message.answer(
                    "✅ Система SaleScrap запущена, но данные еще не собраны."
                )
    except Exception as e:
        await message.answer(f"❌ Ошибка проверки БД: {e}")


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


async def send_parsing_stats(
    platform: str, status: str, rest_count: int, promo_count: int, error_count: int
):
    icon = "✅" if status == "completed" else "❌"
    from datetime import datetime

    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    msg = f"{icon} <b>Парсинг завершен: {platform}</b>\n"
    msg += f"Статус: {status}\n\n"
    msg += "📊 <b>Результаты:</b>\n"
    msg += f"🍽 Найдено заведений: {rest_count}\n"
    msg += f"🏷 Найдено акций: {promo_count}\n"
    msg += f"⚠️ Ошибок: {error_count}\n\n"
    msg += f"🕒 Время (Ташкент): {now_str}"

    await send_telegram_alert(msg)


async def send_daily_digest(top_promos: list):
    """
    Sends the daily top 5 discounts.
    """
    if not top_promos:
        return

    msg = "🌟 <b>ТОП-5 самых выгодных акций в Ташкенте:</b>\n\n"
    for idx, p in enumerate(top_promos[:5], 1):
        msg += f"{idx}. 🟣 <b>{p['restaurant_name']}</b>\n"
        msg += f"   🔥 Скидка: {p['discount_percent']}%\n"
        msg += f"   📝 Скидка: {p['promo_title']}\n"
        msg += f"   💰 Старая цена: {p['original_price']} сум, Новая цена: {p['current_price']} сум\n"

    msg += "\n📱 Откройте дашборд для подробного анализа!"
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
