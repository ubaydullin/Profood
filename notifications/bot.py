import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from database.db import AsyncSessionLocal
from database.models import ParsedPromo
from sqlalchemy import select, func, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from notifications.image_generator import generate_promo_image

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
            stmt = select(func.max(ParsedPromo.timestamp))
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


@dp.message(Command("top"))
async def cmd_top(message: types.Message):
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ParsedPromo)
                .where(
                    ParsedPromo.promo_price.isnot(None),
                    ParsedPromo.discount_percent > 0,
                )
                .order_by(desc(ParsedPromo.discount_percent))
                .limit(1)
            )
            result = await db.execute(stmt)
            promo = result.scalar()

            if not promo:
                await message.answer("Акций не найдено.")
                return

            img_io = generate_promo_image(
                promo.competitor_name,
                promo.item_name,
                promo.base_price,
                promo.promo_price,
                promo.discount_percent,
            )
            photo = BufferedInputFile(img_io.read(), filename="promo.png")

            caption = (
                f"🏆 <b>Топ скидка: {promo.competitor_name}</b>\n{promo.item_name}"
            )

            keyboard = []
            if promo.restaurant_url:
                keyboard.append(
                    [InlineKeyboardButton(text="Открыть 🛒", url=promo.restaurant_url)]
                )
            reply_markup = (
                InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
            )

            await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Пожалуйста, укажите товар. Пример: /search пицца")
        return

    query = args[1].lower()
    try:
        async with AsyncSessionLocal() as db:
            stmt = (
                select(ParsedPromo)
                .where(
                    ParsedPromo.promo_price.isnot(None),
                    func.lower(ParsedPromo.item_name).like(f"%{query}%"),
                )
                .order_by(desc(ParsedPromo.discount_percent))
                .limit(1)
            )

            result = await db.execute(stmt)
            promo = result.scalar()

            if not promo:
                await message.answer(f"Акции по запросу '{query}' не найдены.")
                return

            img_io = generate_promo_image(
                promo.competitor_name,
                promo.item_name,
                promo.base_price,
                promo.promo_price,
                promo.discount_percent,
            )
            photo = BufferedInputFile(img_io.read(), filename="promo.png")

            caption = f"🔍 <b>Найдено по запросу '{query}':</b>\n{promo.competitor_name} - {promo.item_name}"

            keyboard = []
            if promo.restaurant_url:
                keyboard.append(
                    [InlineKeyboardButton(text="Открыть 🛒", url=promo.restaurant_url)]
                )
            reply_markup = (
                InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
            )

            await message.answer_photo(
                photo=photo,
                caption=caption,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


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


async def send_top_dumpers(dumpers: list[tuple[str, int]]):
    """
    Sends a text list of the top 10 establishments with the most promos.
    """
    if not dumpers:
        return

    if BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        print("[Telegram Mock] Top dumpers sent.")
        return

    msg = "📊 <b>Топ-10 заведений по количеству активных акций:</b>\n\n"
    for idx, (name, count) in enumerate(dumpers, 1):
        msg += f"{idx}. <b>{name}</b> — {count} шт.\n"

    try:
        await bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg, parse_mode="HTML")
    except Exception as e:
        print(f"Failed to send top dumpers: {e}")


async def send_digest_with_buttons(promos: list):
    """
    Sends the top promos with inline buttons, attaching an image of the #1 promo.
    """
    if not promos:
        return

    if BOT_TOKEN == "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        print("[Telegram Mock] Digest with buttons generated.")
        return

    msg = "🚨 <b>Внимание! Активность конкурентов!</b> 🚨\n\n"
    for idx, p in enumerate(promos[:5], 1):
        msg += f"{idx}. 🔥 <b>{p['restaurant_name']}</b>\n"
        msg += f"Акция: {p['promo_title']}\n"
        msg += f"Скидка: {p['discount_percent']}%\n\n"

    remaining = len(promos) - 5
    if remaining > 0:
        msg += f"...и еще {remaining} агрессивных акций. Проверьте дашборд."

    keyboard = []
    for idx, p in enumerate(promos[:5], 1):
        url = p.get("restaurant_url") or "https://eda.yandex.uz/"
        btn_text = f"[{idx}] {p['restaurant_name']} (-{p['discount_percent']}%) 🛒"
        keyboard.append([InlineKeyboardButton(text=btn_text, url=url)])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard)

    try:
        # Генерируем картинку для САМОЙ первой (лучшей) акции в списке
        top_promo = promos[0]
        img_io = generate_promo_image(
            top_promo["restaurant_name"],
            top_promo["promo_title"],
            top_promo["original_price"],
            top_promo["current_price"],
            top_promo["discount_percent"],
        )
        photo = BufferedInputFile(img_io.read(), filename="top_digest.png")

        await bot.send_photo(
            chat_id=ADMIN_CHAT_ID,
            photo=photo,
            caption=msg,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception as e:
        print(f"Failed to send digest with photo: {e}")
        # Fallback to text if image generation fails
        try:
            await bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=msg,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
        except Exception as e2:
            print(f"Failed to send fallback digest: {e2}")


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
