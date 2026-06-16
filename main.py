import subprocess
import argparse
import asyncio
import time
from datetime import datetime
from scraper.uzum_scraper import scrape_uzum
from scraper.yandex_scraper import scrape_yandex
from notifications.bot import (
    send_top_dumpers,
    send_digest_with_buttons,
    start_bot_polling,
    close_bot_session,
)
from database.db import init_db


def run_dashboard():
    print("Starting Promotion Intelligence Dashboard...")
    subprocess.run(["uv", "run", "streamlit", "run", "app.py"])


async def run_scraper_async():
    print("Initializing scrapers and database...")
    await init_db()
    try:
        uzum_stats = await scrape_uzum()
        from notifications.bot import send_parsing_stats

        await send_parsing_stats("UZUM", "completed", *uzum_stats)

        yandex_stats = await scrape_yandex()
        await send_parsing_stats("YANDEX", "completed", *yandex_stats)

        print("All scraping tasks completed successfully.")

        # Export to JSON
        import json
        import os
        from sqlalchemy.future import select
        from database.db import AsyncSessionLocal
        from database.models import ParsedPromo

        os.makedirs("data", exist_ok=True)
        export_data = []

        # We find the latest scrape batch by fetching the maximum timestamp minus a small buffer
        # But actually, since the DB will have all history, we export everything for the dashboard
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ParsedPromo))
            promos = result.scalars().all()
            for promo in promos:
                export_data.append(
                    {
                        "timestamp": promo.timestamp.isoformat() + "Z",
                        "aggregator_name": promo.aggregator_name,
                        "competitor_name": promo.competitor_name,
                        "item_category": promo.item_category,
                        "item_name": promo.item_name,
                        "base_price": promo.base_price,
                        "promo_price": promo.promo_price,
                        "discount_percent": promo.discount_percent,
                        "promo_type": promo.promo_type,
                        "promo_target": promo.promo_target,
                        "promo_condition": promo.promo_condition,
                        "discount_threshold": promo.discount_threshold,
                        "is_aggregator_funded": promo.is_aggregator_funded,
                        "search_query_used": promo.search_query_used,
                        "position_in_list": promo.position_in_list,
                        "is_in_carousel": promo.is_in_carousel,
                        "delivery_fee": promo.delivery_fee,
                        "service_fee": promo.service_fee,
                        "min_order_value": promo.min_order_value,
                        "delivery_time_min": promo.delivery_time_min,
                        "delivery_time_max": promo.delivery_time_max,
                        "free_delivery_threshold": promo.free_delivery_threshold,
                        "rating_score": promo.rating_score,
                        "reviews_count": promo.reviews_count,
                    }
                )

        with open("data/export.json", "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"Exported {len(export_data)} records to data/export.json")

        # Fetch top promos from the LATEST batch for the digest
        from datetime import timedelta

        top_promos = []
        if promos:
            latest_time = max(p.timestamp for p in promos)
            recent_threshold = latest_time - timedelta(minutes=30)

            recent_promos = [
                p
                for p in promos
                if p.timestamp >= recent_threshold and p.discount_percent
            ]
            recent_promos.sort(key=lambda x: x.discount_percent, reverse=True)

            unique_recent_promos = []
            seen = set()
            for promo in recent_promos:
                identifier = (
                    str(promo.competitor_name).strip().lower(),
                    str(promo.item_name).strip().lower(),
                )
                if identifier not in seen:
                    seen.add(identifier)
                    unique_recent_promos.append(promo)

            for promo in unique_recent_promos[:5]:
                top_promos.append(
                    {
                        "restaurant_name": promo.competitor_name,
                        "restaurant_url": promo.restaurant_url,
                        "promo_title": promo.item_name,
                        "discount_percent": promo.discount_percent,
                        "original_price": promo.base_price,
                        "current_price": promo.promo_price,
                        "first_seen_at": promo.timestamp,
                    }
                )

            from collections import Counter

            dumper_counts = Counter([p.competitor_name for p in unique_recent_promos])
            top_10_dumpers = dumper_counts.most_common(10)

        # 1. Alert for Top 10 dumpers
        if top_10_dumpers:
            await send_top_dumpers(top_10_dumpers)

        # 2. Alert for aggressive discounts > 20% (ONLY IF NEW BATCH)
        urgent_promos = [p for p in top_promos if p["discount_percent"] >= 20]
        if urgent_promos:
            await send_digest_with_buttons(urgent_promos)

        print("Top 5 Promos:")
        for p in top_promos:
            try:
                print(
                    f"{p['restaurant_name']} - {p['promo_title']} ({p['discount_percent']}%)"
                )
            except UnicodeEncodeError:
                print(
                    f"{p['restaurant_name']} - [Cyrillic Title] ({p['discount_percent']}%)"
                )

        # Uncomment to send via bot if needed
        # await send_daily_digest(top_promos)

    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        await close_bot_session()


def run_scraper():
    asyncio.run(run_scraper_async())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="saleScrap Platform")
    parser.add_argument(
        "--dashboard", action="store_true", help="Run the Streamlit dashboard"
    )
    parser.add_argument("--scrape", action="store_true", help="Run the scrapers once")
    parser.add_argument(
        "--auto", action="store_true", help="Run the scrapers automatically every hour"
    )

    args = parser.parse_args()

    if args.dashboard:
        run_dashboard()
    elif args.scrape:
        run_scraper()
    elif args.auto:
        print("🤖 Режим авто-парсинга включен!")
        print("Парсер будет запускаться каждый час.")
        while True:
            try:
                print(
                    f"\n--- Запуск парсинга: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---"
                )
                run_scraper()
                print(
                    "\n✅ Парсинг завершен. Ожидание 60 минут до следующего запуска..."
                )
                time.sleep(3600)  # Спим 1 час
            except KeyboardInterrupt:
                print("\nОстановка авто-парсера.")
                break
            except Exception as e:
                print(f"\n❌ Критическая ошибка в цикле: {e}")
                print("Повторная попытка через 5 минут...")
                time.sleep(300)
    else:
        # Run background bot
        asyncio.run(start_bot_polling())
