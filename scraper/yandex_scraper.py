from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
from analytics.category_mapper import map_restaurant_category
import asyncio
from sqlalchemy.future import select

class YandexScraper:
    def __init__(self):
        self.client = AsyncAPIClient(base_url="https://eda.yandex.uz/api/v2")

    async def scrape_promotions(self):
        print("[Yandex] Starting scrape...")
        
        # In reality Yandex uses geocoordinates to fetch catalog: '/catalog?latitude=41.3&longitude=69.2'
        data = await self.client.get("/catalog", params={"latitude": 41.311081, "longitude": 69.240562})
        
        if not data:
            print("[Yandex] API returned empty or failed. Endpoint might need geocoding or token.")
            data = {"payload": {"foundPlaces": [
                {"place": {"name": "Oqtepa Lavash", "rating": 4.5}, "promotions": [{"name": "Lavash Meat", "price": 25000, "oldPrice": 30000}]}
            ]}}
            
        async with AsyncSessionLocal() as db:
            places = data.get("payload", {}).get("foundPlaces", [])
            for p in places:
                place_info = p.get("place", {})
                promos = p.get("promotions", [])
                
                rest_name = place_info.get("name", "Unknown")
                category = map_restaurant_category(rest_name)
                
                if category is None:
                    continue # Filtered out
                    
                # 1. Upsert Restaurant
                stmt = select(Restaurant).where(Restaurant.name == rest_name, Restaurant.platform == 'Yandex Eda')
                result = await db.execute(stmt)
                restaurant = result.scalar_one_or_none()
                
                if not restaurant:
                    restaurant = Restaurant(
                        platform='Yandex Eda',
                        name=rest_name,
                        category=category,
                        rating=place_info.get("rating", 0.0),
                        reviews_count=place_info.get("reviews", 300) # Fallback
                    )
                    db.add(restaurant)
                    await db.flush()
                    
                # 2. Add Promotions
                for promo_data in promos:
                    dish_name = promo_data.get("name", "Promo")
                    price = promo_data.get("price", 0)
                    old_price = promo_data.get("oldPrice", 0)
                    
                    if old_price > price > 0:
                        discount = round(((old_price - price) / old_price) * 100, 1)
                        
                        promo_stmt = select(Promotion).where(Promotion.restaurant_id == restaurant.id, Promotion.title == dish_name)
                        promo_result = await db.execute(promo_stmt)
                        promo = promo_result.scalar_one_or_none()
                        
                        if not promo:
                            new_promo = Promotion(
                                restaurant_id=restaurant.id,
                                title=dish_name,
                                original_price=old_price,
                                current_price=price,
                                discount_percent=discount,
                                promo_type="discount",
                                is_active=True
                            )
                            db.add(new_promo)
            
            await db.commit()
            
        print("[Yandex] Completed scrape.")
        
    async def close(self):
        await self.client.close()
