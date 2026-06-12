import subprocess
import argparse
import asyncio
from scraper.uzum_scraper import scrape_uzum
from scraper.yandex_scraper import scrape_yandex
from notifications.bot import send_telegram_alert, send_daily_digest, start_bot_polling, close_bot_session
from database.db import init_db

def run_dashboard():
    print("Starting Promotion Intelligence Dashboard...")
    subprocess.run(["uv", "run", "streamlit", "run", "app.py"])

async def run_scraper_async():
    print("Initializing scrapers and database...")
    await init_db()
    try:
        await scrape_uzum()
        await scrape_yandex()
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
                    "timestamp": promo.first_seen_at.isoformat() + "Z",
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
        
        # Fetch top promos from DB for the digest
        from datetime import datetime, timedelta
        yesterday = datetime.utcnow() - timedelta(days=1)
        
        async with AsyncSessionLocal() as db:
            stmt = (
                select(Promotion, Restaurant)
                .join(Restaurant)
                .where(Promotion.is_active == True)
                .where(Promotion.first_seen_at >= yesterday)
                .order_by(Promotion.discount_percent.desc())
                .limit(5)
            )
            result = await db.execute(stmt)
            top_promos = []
            for promo, rest in result.all():
                top_promos.append({
                    'restaurant_name': rest.name,
                    'promo_title': promo.title,
                    'discount_percent': promo.discount_percent,
                    'original_price': promo.original_price,
                    'current_price': promo.current_price
                })
        
        # 1. Alert for aggressive discounts > 20%
        for promo in top_promos:
            if promo['discount_percent'] >= 20:
                await send_telegram_alert(f"🚨 <b>Агрессивная скидка!</b>\n{promo['restaurant_name']} снизил цену на {promo['promo_title']} на {promo['discount_percent']}%!")
        
        # 2. Daily Digest (Top 5)
        await send_daily_digest(top_promos)
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
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
