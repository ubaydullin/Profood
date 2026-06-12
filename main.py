import subprocess
import argparse
import asyncio
from scraper.uzum_scraper import UzumScraper
from scraper.yandex_scraper import YandexScraper
from notifications.bot import send_telegram_alert

def run_dashboard():
    print("Starting Promotion Intelligence Dashboard...")
    subprocess.run(["uv", "run", "streamlit", "run", "app.py"])

async def run_scraper_async():
    print("Initializing scrapers...")
    uzum = UzumScraper()
    yandex = YandexScraper()
    
    try:
        await asyncio.gather(
            uzum.scrape_promotions(),
            yandex.scrape_promotions()
        )
        print("All scraping tasks completed successfully.")
        
        await send_telegram_alert("[Alert] Anomaly Detected: 'Lavash Meat' in Evos is 20% more expensive than Oqtepa Lavash, but has 40% more orders! Brand loyalty is strong.")
        
    except Exception as e:
        print(f"Error during scraping: {e}")
    finally:
        await uzum.close()
        await yandex.close()

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
        print("Please specify --dashboard or --scrape")
