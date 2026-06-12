from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
import asyncio

class UzumScraper:
    def __init__(self):
        self.client = AsyncAPIClient(base_url="https://api.uzum.uz/tezkor") # Mock base URL

    async def scrape_promotions(self):
        print("Scraping Uzum Tezkor promotions...")
        # Mock logic: in reality, parse JSON or HTML here
        # response = await self.client.get("/promotions")
        await asyncio.sleep(1) # Simulate network delay
        
        async with AsyncSessionLocal() as db:
            # Upsert mock restaurant
            # In a real app, use SQLAlchemy `select` and `merge` or Postgres `INSERT ... ON CONFLICT`
            new_promo = Promotion(
                title="Mock Uzum Promo",
                discount_percent=15.0,
                promo_type="discount",
                is_active=True
            )
            db.add(new_promo)
            # await db.commit() # Disabled for stub
        
        print("Completed Uzum Tezkor scrape.")
        
    async def close(self):
        await self.client.close()
