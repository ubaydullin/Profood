import subprocess
import argparse
import asyncio
from scraper.uzum_scraper import UzumScraper
from scraper.yandex_scraper import YandexScraper
from scraper.express24_scraper import Express24Scraper
from notifications.bot import send_telegram_alert, send_daily_digest, start_bot_polling, close_bot_session

def run_dashboard():
    print("Starting Promotion Intelligence Dashboard...")
    subprocess.run(["uv", "run", "streamlit", "run", "app.py"])

async def run_scraper_async():
    print("Initializing scrapers...")
    uzum = UzumScraper()
    yandex = YandexScraper()
    express = Express24Scraper()
    
    try:
        await asyncio.gather(
            uzum.scrape_promotions(),
            yandex.scrape_promotions(),
            express.scrape_promotions()
        )
        print("All scraping tasks completed successfully.")
        
        # In a real app we'd fetch this from DB, using mock data here
        mock_promos = [
            {'restaurant_name': 'Yapona Mama', 'promo_title': 'Philadelphia Sushi', 'discount_percent': 30, 'original_price': 100000, 'current_price': 70000},
            {'restaurant_name': 'FeedUp', 'promo_title': 'Cheese Burger', 'discount_percent': 20, 'original_price': 35000, 'current_price': 28000}
        ]
        
        # 1. Alert for aggressive discounts > 30%
        for promo in mock_promos:
            if promo['discount_percent'] >= 30:
                await send_telegram_alert(f"🚨 <b>Aggressive Discount Alert!</b>\n{promo['restaurant_name']} dropped price on {promo['promo_title']} by {promo['discount_percent']}%!")
        
        # 2. Daily Digest (Top 5)
        await send_daily_digest(mock_promos)
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        await uzum.close()
        await yandex.close()
        await express.close()
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
