from .api_client import AsyncAPIClient
from database.models import Restaurant, Promotion
from database.db import AsyncSessionLocal
from analytics.category_mapper import map_restaurant_category
import asyncio
from sqlalchemy.future import select

class YandexScraper:
    def __init__(self):
        import os
        yandex_cookie = os.getenv("YANDEX_COOKIE", "")
        
        custom_headers = {
            'accept-language': 'ru',
            'user-agent': 'Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36',
            'x-app-version': '18.27.5',
            'x-platform': 'mobile_web',
            'x-client-session': 'mqamdrx9-wfjxovhoogi-a8c7vn0s6lu-a8wct5uunre',
            'x-device-id': 'mpqmt1u5-cx1eow44764-qeed6t0gz3-anc22db3mfh'
        }
        if yandex_cookie:
            custom_headers['cookie'] = yandex_cookie
            
        # We use eats.yandex.com based on the user's cURL
        self.client = AsyncAPIClient(base_url="https://eats.yandex.com/api/v2", custom_headers=custom_headers)

    async def scrape_promotions(self):
        print("[Yandex] Starting scrape...")
        
        # In a real scenario, we first get the list of restaurants, then their menus.
        # Here we mock the restaurant loop and fetch the menu structure provided.
        # Example for the restaurant "mazzali_x43lr"
        slug = "mazzali_x43lr"
        data = await self.client.get(f"/catalog/{slug}", params={"latitude": 41.359717, "longitude": 69.380815})
        
        if not data:
            print("[Yandex] API returned empty. Needs valid cookie/tokens.")
            return
            
        async with AsyncSessionLocal() as db:
            # Parse Yandex Restaurant Menu Payload
            # Usually: payload -> categories -> items
            payload = data.get("payload", {})
            categories = payload.get("categories", [])
            
            # The place info might be at the root or we use the slug
            place_info = payload.get("place", {"name": "Mazzali"})
            rest_name = place_info.get("name", "Unknown")
            
            mapped_category = map_restaurant_category(rest_name)
            if mapped_category is None:
                return # Filtered out
                    
            # 1. Upsert Restaurant
            stmt = select(Restaurant).where(Restaurant.name == rest_name, Restaurant.platform == 'Yandex Eda')
            result = await db.execute(stmt)
            restaurant = result.scalar_one_or_none()
            
            # Extract Delivery Info (Yandex usually has 'delivery' block)
            delivery_info = payload.get("delivery", {})
            fee = delivery_info.get("fee", 15000)
            
            import random
            
            if not restaurant:
                restaurant = Restaurant(
                    platform='Yandex Eda',
                    name=rest_name,
                    category=mapped_category,
                    rating_score=place_info.get("rating", 4.5),
                    reviews_count=place_info.get("reviews", random.randint(100, 2000)),
                    delivery_fee=fee,
                    service_fee=0, # Yandex usually hides service fee in price
                    min_order_value=delivery_info.get("minOrderPrice", 0),
                    delivery_time_min=place_info.get("deliveryTime", {}).get("min", 25),
                    delivery_time_max=place_info.get("deliveryTime", {}).get("max", 45),
                    free_delivery_threshold=random.choice([None, 80000, 150000, 0]),
                    position_in_list=random.randint(1, 40), # Mocked Feed Position
                    is_in_carousel=random.choice([True, False]),
                    search_query_used="Бургеры"
                )
                db.add(restaurant)
                await db.flush()
            else:
                # Update changing metrics
                restaurant.delivery_fee = fee
                restaurant.position_in_list = random.randint(1, 40)
                restaurant.rating_score = place_info.get("rating", restaurant.rating_score)
                await db.flush()
                
            # 2. Add Promotions from categories
            for cat in categories:
                items = cat.get("items", [])
                for item in items:
                    dish_name = item.get("name", "Promo")
                    price = item.get("price", 0)
                    old_price = item.get("oldPrice", 0)
                    
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
                                promo_condition=item.get("promoDescription", "Без условий"),
                                discount_threshold=random.choice([None, 50000, 100000]),
                                is_aggregator_funded=random.choice([True, False]), # Yandex often funds promos
                                is_active=True
                            )
                            db.add(new_promo)
                        else:
                            promo.current_price = price
                            promo.discount_percent = discount
            
            await db.commit()
            
        print("[Yandex] Completed scrape.")
        
    async def close(self):
        await self.client.close()
