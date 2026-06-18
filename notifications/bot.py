import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from dotenv import load_dotenv
from database.db import AsyncSessionLocal
from database.models import ParsedPromo
from sqlalchemy import select, func, desc
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.filters.callback_data import CallbackData
from notifications.image_generator import generate_item_card

load_dotenv()

class SearchCallback(CallbackData, prefix="search"):
    query: str
    page: int

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
                .limit(5)
            )
            result = await db.execute(stmt)
            promos = result.scalars().all()

            if not promos:
                await message.answer("Акций не найдено.")
                return

            promo = promos[0]
            img_io = await generate_item_card(
                promo.competitor_name,
                promo.item_name,
                promo.base_price,
                promo.promo_price,
                promo.discount_percent,
                promo.aggregator_name,
                promo.picture_url
            )
            photo = BufferedInputFile(img_io.read(), filename="promo.png")

            caption = "🏆 <b>Топ-5 лучших скидок:</b>\n\n"
            for idx, p in enumerate(promos, 1):
                caption += f"{idx}. {p.competitor_name} - {p.item_name} (-{p.discount_percent}%)\n"

            keyboard = []
            for idx, p in enumerate(promos, 1):
                if p.restaurant_url:
                    keyboard.append(
                        [InlineKeyboardButton(text=f"[{idx}] {p.competitor_name} 🛒", url=p.restaurant_url)]
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


async def get_search_results(query: str, page: int):
    async with AsyncSessionLocal() as db:
        stmt = (
            select(ParsedPromo)
            .where(
                ParsedPromo.promo_price.isnot(None),
                func.lower(ParsedPromo.item_name).like(f"%{query}%"),
            )
            .group_by(ParsedPromo.competitor_name, ParsedPromo.item_name)
            .order_by(desc(func.max(ParsedPromo.discount_percent)))
            .limit(11).offset(page * 10)
        )
        result = await db.execute(stmt)
        return result.scalars().all()


@dp.message(Command("search"))
async def cmd_search(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Пожалуйста, укажите товар. Пример: /search пицца")
        return

    query = args[1].lower()
    try:
        promos = await get_search_results(query, 0)
        if not promos:
            await message.answer(f"Акции по запросу '{query}' не найдены.")
            return

        has_next = len(promos) > 10
        display_promos = promos[:10]

        promo = display_promos[0]
        img_io = await generate_item_card(
            promo.competitor_name,
            promo.item_name,
            promo.base_price,
            promo.promo_price,
            promo.discount_percent,
            promo.aggregator_name,
            promo.picture_url
        )
        photo = BufferedInputFile(img_io.read(), filename="promo.png")

        caption = f"🔍 <b>Лучшее совпадение по '{query}':</b>\n{promo.competitor_name} - {promo.item_name} (-{promo.discount_percent}%)\n"
        
        if len(display_promos) > 1:
            caption += "\n📋 <b>Другие варианты (Стр. 1):</b>\n"
            for idx, p in enumerate(display_promos[1:], 2):
                caption += f"{idx}. {p.competitor_name} - {p.item_name} (-{p.discount_percent}%)\n"

        keyboard = []
        for idx, p in enumerate(display_promos, 1):
            if p.restaurant_url:
                keyboard.append(
                    [InlineKeyboardButton(text=f"[{idx}] {p.competitor_name} 🛒", url=p.restaurant_url)]
                )
                
        nav_buttons = []
        if has_next:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=SearchCallback(query=query[:20], page=1).pack()))
        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

        await message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
    except Exception as e:
        await message.answer(f"Ошибка: {e}")


@dp.callback_query(SearchCallback.filter())
async def process_search_page(callback: types.CallbackQuery, callback_data: SearchCallback):
    query = callback_data.query
    page = callback_data.page

    try:
        promos = await get_search_results(query, page)
        
        if not promos:
            await callback.answer("Больше результатов нет", show_alert=True)
            return

        has_next = len(promos) > 10
        display_promos = promos[:10]

        caption = f"🔍 <b>Результаты по '{query}' (Стр. {page + 1}):</b>\n\n"
        for idx, p in enumerate(display_promos, page * 10 + 1):
            caption += f"{idx}. {p.competitor_name} - {p.item_name} (-{p.discount_percent}%)\n"

        keyboard = []
        for idx, p in enumerate(display_promos, page * 10 + 1):
            if p.restaurant_url:
                keyboard.append(
                    [InlineKeyboardButton(text=f"[{idx}] {p.competitor_name} 🛒", url=p.restaurant_url)]
                )
        
        nav_buttons = []
        if page > 0:
            nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=SearchCallback(query=query[:20], page=page - 1).pack()))
        if has_next:
            nav_buttons.append(InlineKeyboardButton(text="Вперед ➡️", callback_data=SearchCallback(query=query[:20], page=page + 1).pack()))
        if nav_buttons:
            keyboard.append(nav_buttons)

        reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None

        await callback.message.edit_caption(
            caption=caption,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )
        await callback.answer()
    except Exception as e:
        await callback.answer(f"Ошибка загрузки страницы: {e}")


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
    platform: str, status: str, rest_count: int, promo_count: int, error_count: int, top_promo=None
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

    if top_promo and BOT_TOKEN != "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11":
        try:
            img_io = await generate_item_card(
                top_promo.competitor_name,
                top_promo.item_name,
                top_promo.base_price,
                top_promo.promo_price,
                top_promo.discount_percent,
                platform,
                top_promo.picture_url
            )
            photo = BufferedInputFile(img_io.read(), filename="stats.png")
            keyboard = []
            if top_promo.restaurant_url:
                keyboard.append([InlineKeyboardButton(text=f"Открыть лучшую акцию 🛒", url=top_promo.restaurant_url)])
            reply_markup = InlineKeyboardMarkup(inline_keyboard=keyboard) if keyboard else None
            
            await bot.send_photo(
                chat_id=ADMIN_CHAT_ID,
                photo=photo,
                caption=msg,
                parse_mode="HTML",
                reply_markup=reply_markup,
            )
            return
        except Exception as e:
            print(f"Failed to send parsing stats with photo: {e}")

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
        img_io = await generate_item_card(
            top_promo["restaurant_name"],
            top_promo["promo_title"],
            top_promo["original_price"],
            top_promo["current_price"],
            top_promo["discount_percent"],
            top_promo.get("aggregator_name", "Yandex"),
            top_promo.get("picture_url")
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
