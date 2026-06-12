import subprocess
import argparse
import asyncio
from scraper.uzum_scraper import UzumScraper
from scraper.yandex_scraper import YandexScraper
from notifications.bot import send_telegram_alert, send_daily_digest, start_bot_polling, close_bot_session
from database.db import init_db

def run_dashboard():
    print("Starting Promotion Intelligence Dashboard...")
    subprocess.run(["uv", "run", "streamlit", "run", "app.py"])

async def run_scraper_async():
    print("Initializing scrapers and database...")
    await init_db()
    uzum = UzumScraper()
    yandex = YandexScraper()
    
    try:
        await asyncio.gather(
            uzum.scrape_promotions(),
            yandex.scrape_promotions()
        )
        print("All scraping tasks completed successfully.")
        
        # Export to JSON
        import json
        import os
        from sqlalchemy.future import select
        from database.db import AsyncSessionLocal
        from database.models import Promotion, Restaurant
        
        os.makedirs("data", exist_ok=True)
        export_data = []
        
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(Promotion, Restaurant)
                .join(Restaurant)
            )
            for promo, rest in result.all():
                export_data.append({
                    "timestamp": promo.snapshot_at.isoformat() + "Z",
                    "aggregator_name": rest.platform,
                    "competitor_name": rest.name,
                    "item_category": rest.category,
                    "item_name": promo.title,
                    "base_price": promo.original_price or promo.current_price,
                    "promo_price": promo.current_price,
                    "discount_percent": promo.discount_percent,
                    "promo_type": promo.promo_type,
                    "promo_target": promo.promo_target,
                    "promo_condition": promo.promo_condition,
                    "discount_threshold": promo.discount_threshold,
                    "is_aggregator_funded": promo.is_aggregator_funded,
                    "search_query_used": rest.search_query_used,
                    "position_in_list": rest.position_in_list,
                    "is_in_carousel": rest.is_in_carousel,
                    "delivery_fee": rest.delivery_fee,
                    "service_fee": rest.service_fee,
                    "min_order_value": rest.min_order_value,
                    "delivery_time_min": rest.delivery_time_min,
                    "delivery_time_max": rest.delivery_time_max,
                    "free_delivery_threshold": rest.free_delivery_threshold,
                    "rating_score": rest.rating_score,
                    "reviews_count": rest.reviews_count
                })
        
        with open("data/export.json", "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)
            
        print(f"Exported {len(export_data)} records to data/export.json")
        
        # In a real app we'd fetch this from DB, using mock data here
        mock_promos = [
            {'restaurant_name': 'Yapona Mama', 'promo_title': 'Philadelphia Sushi', 'discount_percent': 30, 'original_price': 100000, 'current_price': 70000},
            {'restaurant_name': 'FeedUp', 'promo_title': 'Cheese Burger', 'discount_percent': 20, 'original_price': 35000, 'current_price': 28000}
        ]
        
        # 1. Alert for aggressive discounts > 30%
        for promo in mock_promos:
            if promo['discount_percent'] >= 30:
                await send_telegram_alert(f"🚨 <b>Агрессивная скидка!</b>\n{promo['restaurant_name']} снизил цену на {promo['promo_title']} на {promo['discount_percent']}%!")
        
        # 2. Daily Digest (Top 5)
        await send_daily_digest(mock_promos)
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        await uzum.close()
        await yandex.close()
        await close_bot_session()

def run_scraper():
    asyncio.run(run_scraper_async())
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="saleScrap Platform")
    parser.add_argument("--dashboard", action="store_true", help="Run the Streamlit dashboard")
    parser.add_argument("--scrape", action="store_true", help="Run the scrapers")
    
    args = parser.parse_args()
    
    if args.dashboard:
        run_dashboard()
    elif args.scrape:
        run_scraper()
    else:
        # Run background bot
        asyncio.run(start_bot_polling())
