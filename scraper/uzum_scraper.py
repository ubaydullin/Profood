from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
from analytics.category_mapper import map_restaurant_category
import asyncio
from sqlalchemy.future import select

class UzumScraper:
    def __init__(self):
        self.client = AsyncAPIClient(base_url="https://www.uzumtezkor.uz/api/v2")
        
        self.client.headers.update({
            'accept': '*/*',
            'accept-language': 'ru',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36',
        })
        
        import os
        uzum_cookie = os.getenv("UZUM_COOKIE")
        uzum_auth = os.getenv("UZUM_AUTH_TOKEN")
        if uzum_cookie:
            self.client.headers['cookie'] = uzum_cookie
        if uzum_auth:
            self.client.headers['authorization'] = uzum_auth

    async def scrape_promotions(self):
        print("[Uzum] Starting scrape...")
        
        # Example vendor id from user's cURL
        vendor_id = "bad11656-434c-4549-88c7-1b6d11da5dc1"
        data = await self.client.get(f"/vendors/{vendor_id}/catalog", params={"lat": 41.353617, "long": 69.345498}) 
        
        if not data:
            print("[Uzum] API returned empty. Needs valid cookie/tokens.")
            return
        
        async with AsyncSessionLocal() as db:
            # Usually Uzum payload has sections -> items
            payload = data.get("payload", data) # Adapt to their JSON structure
            sections = payload.get("sections", [])
            
            # The restaurant name might be embedded in the header/vendor info
            # We'll use a placeholder for now since catalog usually just returns items
            rest_name = payload.get("vendor", {}).get("name", "Uzum Vendor")
            
            category = map_restaurant_category(rest_name)
            if category is None:
                return # Filtered out
                
            # 1. Upsert Restaurant
            stmt = select(Restaurant).where(Restaurant.name == rest_name, Restaurant.platform == 'Uzum Tezkor')
            result = await db.execute(stmt)
            restaurant = result.scalar_one_or_none()
            
            if not restaurant:
                restaurant = Restaurant(
                    platform='Uzum Tezkor',
                    name=rest_name,
                    category=category,
                    rating=payload.get("vendor", {}).get("rating", 0.0),
                    reviews_count=payload.get("vendor", {}).get("reviews", 500) # Fallback
                )
                db.add(restaurant)
                await db.flush() # To get ID
                
            # 2. Add Promotion
            for section in sections:
                items = section.get("items", [])
                for item in items:
                    dish_name = item.get("name", "Promo")
                    price = item.get("price", 0)
                    old_price = item.get("old_price", 0)
                    
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
            
        print("[Uzum] Completed scrape.")
        
    async def close(self):
        await self.client.close()
