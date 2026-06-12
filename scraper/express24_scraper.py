from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
from analytics.category_mapper import map_restaurant_category
import asyncio

class Express24Scraper:
    def __init__(self):
        self.client = AsyncAPIClient(base_url="https://express24.uz/api")

    async def scrape_promotions(self):
        print("Scraping Express24 promotions...")
        await asyncio.sleep(1.2) # Simulate network delay
        
        # Simulated data payload
        restaurants_data = [
            {"name": "KFC", "promo": "Bucket", "discount": 10, "old": 70000, "new": 63000, "reviews": 6000},
            {"name": "Apteka 999", "promo": "Vitamins", "discount": 20, "old": 100000, "new": 80000, "reviews": 500}
        ]
        
        async with AsyncSessionLocal() as db:
            for item in restaurants_data:
                category = map_restaurant_category(item["name"])
                if category is None:
                    print(f"[Filter] Ignored non-food business: {item['name']}")
                    continue
                
                # In real app: Insert to database
                # print(f"Inserted promo for {item['name']}")
            
        print("Completed Express24 scrape.")
        
    async def close(self):
        await self.client.close()
