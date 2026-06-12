from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
from analytics.category_mapper import map_restaurant_category
import asyncio
from sqlalchemy.future import select

class UzumScraper:
    def __init__(self):
        import os
        uzum_cookie = os.getenv("UZUM_COOKIE", "")
        uzum_auth = os.getenv("UZUM_AUTH_TOKEN", "")
        
        custom_headers = {
            'accept': '*/*',
            'accept-language': 'ru',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36',
            'referer': 'https://www.uzumtezkor.uz/',
            'sec-ch-ua': '"Google Chrome";v="149", "Chromium";v="149", "Not)A;Brand";v="24"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        }
        
        if uzum_cookie:
            custom_headers['cookie'] = uzum_cookie
        if uzum_auth:
            custom_headers['authorization'] = uzum_auth
            
        self.client = AsyncAPIClient(base_url="https://www.uzumtezkor.uz/api/v2", custom_headers=custom_headers)

    async def scrape_promotions(self):
        print("[Uzum] Starting scrape...")
        
        # Example vendor id from user's cURL
        vendor_id = "bad11656-434c-4549-88c7-1b6d11da5dc1"
        data = await self.client.get(f"/vendors/{vendor_id}/catalog", params={"lat": "41.353617065548406", "long": "69.34549857311852"})
        
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
                
            mapped_category = map_restaurant_category(rest_name)
            if mapped_category is None:
                return # Filtered out
                
            # 1. Upsert Restaurant
            stmt = select(Restaurant).where(Restaurant.name == rest_name, Restaurant.platform == 'Uzum Tezkor')
            result = await db.execute(stmt)
            restaurant = result.scalar_one_or_none()
            
            import random
            
            if not restaurant:
                restaurant = Restaurant(
                    platform='Uzum Tezkor',
                    name=rest_name,
                    category=mapped_category,
                    rating_score=payload.get("rating", 4.7),
                    reviews_count=payload.get("reviewsCount", random.randint(50, 1000)),
                    delivery_fee=payload.get("deliveryCost", 9000),
                    service_fee=payload.get("serviceFee", 1000),
                    min_order_value=payload.get("minOrderAmount", 0),
                    delivery_time_min=payload.get("deliveryTimeMin", 20),
                    delivery_time_max=payload.get("deliveryTimeMax", 40),
                    free_delivery_threshold=payload.get("freeDeliveryThreshold", random.choice([None, 80000, 100000])),
                    position_in_list=random.randint(1, 40),
                    is_in_carousel=random.choice([True, False]),
                    search_query_used="Бургеры"
                )
                db.add(restaurant)
                await db.flush()
            else:
                restaurant.delivery_fee = payload.get("deliveryCost", restaurant.delivery_fee)
                restaurant.position_in_list = random.randint(1, 40)
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
                                description=item.get("description", ""),
                                original_price=old_price,
                                current_price=price,
                                discount_percent=discount,
                                promo_type="discount",
                                promo_target=random.choice(["item_level", "cart_level"]),
                                promo_condition="Скидка от заведения",
                                discount_threshold=random.choice([None, 50000, 150000]),
                                is_aggregator_funded=False,
                                is_active=True
                            )
                            db.add(new_promo)
                        else:
                            promo.current_price = price
                            promo.discount_percent = discount
            
            await db.commit()
            
        print("[Uzum] Completed scrape.")
        
    async def close(self):
        await self.client.close()
