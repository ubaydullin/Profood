"""Uzum Tezkor scraper.

Uses native API requests to extract restaurant menu data with pricing.
Bypasses anti-bot by extracting accessToken from the initial page payload
and using curl_cffi via AsyncAPIClient.

API endpoints discovered:
- /api/v1/vendors — list of restaurants at a geo location
- /api/v1/vendors/{uuid}/catalog — individual restaurant data
"""

import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import json
from datetime import datetime
from bs4 import BeautifulSoup


from analytics.category_mapper import map_restaurant_category, normalize_restaurant_name
from database.db import AsyncSessionLocal
from database.models import ParsedPromo
from scraper.api_client import AsyncAPIClient
from scraper.geo_rotator import get_random_point


async def _get_uzum_token(client: AsyncAPIClient) -> str | None:
    """Fetch the Uzum homepage and extract the accessToken from __NEXT_DATA__."""
    print("[Uzum Tezkor] Fetching homepage to get auth token...")
    resp = await client.client.get("https://www.uzumtezkor.uz/ru")
    soup = BeautifulSoup(resp.text, "html.parser")
    script = soup.find("script", id="__NEXT_DATA__")

    if not script:
        print("[Uzum Tezkor] ERROR: Could not find __NEXT_DATA__ script.")
        return None

    try:
        data = json.loads(script.string)
        token = data.get("props", {}).get("pageProps", {}).get("accessToken")
        if token:
            print(f"[Uzum Tezkor] Successfully extracted token (len: {len(token)})")
            return token
    except Exception as e:
        print(f"[Uzum Tezkor] ERROR: Failed to parse token: {e}")

    return None


async def _fetch_all_vendors(
    client: AsyncAPIClient, lat: float, lon: float
) -> list[dict]:
    """Fetch all vendors at the given coordinates."""
    vendors = []
    limit = 100
    offset = 0
    total = None

    while True:
        params = {"lat": lat, "long": lon, "limit": limit, "offset": offset}
        res = await client.get("/api/v1/vendors", params=params)
        if not res or "vendors" not in res:
            break

        batch = res.get("vendors", [])
        if not batch:
            break

        vendors.extend(batch)
        if total is None:
            total = res.get("total", len(batch))
            print(f"[Uzum Tezkor] Found {total} vendors at location.")

        offset += limit
        if offset >= total or len(batch) < limit:
            break

    return vendors


async def _fetch_vendor_catalog(
    client: AsyncAPIClient, vendor_id: str, lat: float, lon: float
) -> dict | None:
    """Fetch catalog for a specific vendor."""
    params = {"lat": lat, "long": lon}
    # Multiple endpoints might exist depending on app version
    endpoints = [
        f"/api/v1/vendors/{vendor_id}/catalog",
        f"/api/v2/vendors/{vendor_id}/catalog",
    ]

    for ep in endpoints:
        res = await client.get(ep, params=params)
        if res and "categories" in res:
            return res

    return None


async def scrape_uzum() -> tuple[int, int, int]:
    """Main entry point for the Uzum Tezkor scraper.

    Uses native API requests to fetch all vendors and their catalogs.

    Returns:
        Tuple of (restaurants_count, promos_count, errors_count).
    """
    print("[Uzum Tezkor] Starting native API scrape...")

    # Initialize basic client to get token
    base_client = AsyncAPIClient(base_url="https://www.uzumtezkor.uz")
    token = await _get_uzum_token(base_client)
    await base_client.close()

    if not token:
        return 0, 0, 1

    # Re-initialize client with token
    client = AsyncAPIClient(
        base_url="https://www.uzumtezkor.uz",
        custom_headers={
            "Authorization": f"Bearer {token}",
            "x-platform": "8",
            "x-platform-version": "1.104.20",
        },
    )

    geo = get_random_point()
    print(
        f"[Uzum Tezkor] Using geo point: {geo['name']} ({geo['latitude']:.4f}, {geo['longitude']:.4f})"
    )

    vendors = await _fetch_all_vendors(client, geo["latitude"], geo["longitude"])
    if not vendors:
        print("[Uzum Tezkor] No vendors found.")
        await client.close()
        return 0, 0, 0

    print(f"[Uzum Tezkor] Loaded {len(vendors)} vendors from API.")

    results = []

    # Process vendors
    RETAIL_TRASH = {
        "makro",
        "zoo planeta",
        "korzinka go",
        "the loaf",
        "korzinka",
        "apteka",
        "pharmacy",
        "texnomart",
        "baraka",
        "барака",
    }

    for idx, vendor_data in enumerate(vendors):
        info = vendor_data.get("info", {})
        vendor_id = info.get("id")
        title = info.get("name", vendor_data.get("title", "Unknown"))
        alias = info.get("alias") or info.get("slug")
        restaurant_url = (
            f"https://www.uzumtezkor.uz/ru/restaurant/{alias}" if alias else None
        )

        # Skip retail trash to avoid data pollution
        if any(trash in title.lower() for trash in RETAIL_TRASH):
            print(f"[Uzum Tezkor] Skipping retail/trash: {title}")
            continue
        # Extract rating and reviews
        raw_rating = info.get("rating")
        rating = 4.5
        if isinstance(raw_rating, dict):
            rating = float(raw_rating.get("gradeFloat", raw_rating.get("grade", 4.5)))
        elif isinstance(raw_rating, (int, float)):
            rating = float(raw_rating)
        elif isinstance(raw_rating, str) and raw_rating.replace(".", "", 1).isdigit():
            rating = float(raw_rating)

        # Вытаскиваем отзывы (если API их прячет, ставим 50, чтобы пузырек на графике не исчезал)
        reviews = info.get(
            "reviewsCount", info.get("feedbacksCount", vendor_data.get("reviews", 50))
        )

        # Извлекаем доставку из реальной структуры API:
        # - receiving.delivery.price.value — фактическая стоимость доставки
        # - offer.deliveryAmount — стоимость до применения скидки
        # - offer.minOrderAmount — минимальная сумма заказа
        # - offer.minDeliveryTime / maxDeliveryTime — время доставки
        receiving = vendor_data.get("receiving", {})
        receiving_delivery = receiving.get("delivery", {})
        receiving_price = receiving_delivery.get("price", {})

        offer = vendor_data.get("offer", {})

        # Стоимость доставки: берём фактическую (value), если есть,
        # иначе — originalValue из receiving, иначе — deliveryAmount из offer.
        raw_delivery = receiving_price.get("value")
        if raw_delivery is None:
            raw_delivery = receiving_price.get("originalValue")
        if raw_delivery is None:
            raw_delivery = offer.get("deliveryAmount", 0)
        # Цены в API приходят в тиинах (×100), конвертируем в сумы
        delivery_fee = float(raw_delivery) / 100.0 if raw_delivery else 0.0

        # Порог бесплатной доставки: если receiving показывает value=0,
        # а originalValue > 0, значит доставка бесплатная при текущих условиях
        free_delivery_threshold = None
        if receiving_price.get("value") == 0 and receiving_price.get("originalValue", 0) > 0:
            # Минимальный заказ может быть порогом
            raw_min = offer.get("minOrderAmount", 0)
            if raw_min:
                free_delivery_threshold = float(raw_min) / 100.0

        # Минимальный заказ
        raw_min_order = offer.get("minOrderAmount", 0)
        min_order = float(raw_min_order) / 100.0 if raw_min_order else 0.0

        # Реальное время доставки из API (без хардкода)
        delivery_time_min = offer.get("minDeliveryTime")
        delivery_time_max = offer.get("maxDeliveryTime")

        if not vendor_id:
            continue

        print(
            f"[Uzum Tezkor] ({idx + 1}/{len(vendors)}) Fetching catalog for {title}..."
        )
        catalog = await _fetch_vendor_catalog(
            client, vendor_id, geo["latitude"], geo["longitude"]
        )

        if not catalog:
            print(f"[Uzum Tezkor] Could not fetch catalog for {title}")
            continue

        items = []
        # Парсим товары из categories.items (старый формат)
        for cat in catalog.get("categories", []):
            for item in cat.get("items", []):
                parsed = _parse_uzum_item(item)
                if parsed:
                    items.append(parsed)

        # В новом формате API товары лежат в отдельном списке 'products'
        for item in catalog.get("products", []):
            parsed = _parse_uzum_item(item)
            if parsed:
                items.append(parsed)

        if not items:
            print(f"[Uzum Tezkor] No items found for {title}")
            continue

        promo_count = sum(1 for it in items if it["has_promo"])
        print(
            f"[Uzum Tezkor] Scraped {title}: {len(items)} items, {promo_count} promos"
        )

        results.append(
            {
                "name": title.strip().title(),
                "restaurant_url": restaurant_url,
                "position": idx + 1,
                "rating": rating,
                "reviews": reviews,
                "delivery_fee": delivery_fee,
                "min_order": min_order,
                "free_delivery_threshold": free_delivery_threshold,
                "delivery_time_min": delivery_time_min,
                "delivery_time_max": delivery_time_max,
                "items": items,
            }
        )

    await client.close()

    if not results:
        return 0, 0, 1

    stats = await process_uzum_results(results)
    print("[Uzum] Completed scrape.")
    return stats


def _parse_uzum_item(item: dict) -> dict | None:
    """Parse a single Uzum Tezkor menu item.

    Args:
        item: Raw item dict from the Uzum API.

    Returns:
        Parsed item dict, or None if invalid.
    """
    name = item.get("name") or item.get("title")
    if not name:
        return None

    # Handle native API prices format
    price_obj = item.get("price")
    old_price_obj = item.get("oldPrice")

    price = 0
    old_price = 0

    if isinstance(price_obj, dict):
        price = price_obj.get("value", 0) / 100.0
    elif isinstance(price_obj, (int, float)):
        price = float(price_obj)

    if isinstance(old_price_obj, dict):
        old_price = old_price_obj.get("value", 0) / 100.0
    elif isinstance(old_price_obj, (int, float)):
        old_price = float(old_price_obj)
    elif old_price_obj is None:
        old_price = price

    if price <= 0:
        # Try prices array fallback
        prices = item.get("prices", [])
        if prices:
            sorted_prices = sorted(
                prices, key=lambda x: x.get("sum", x.get("price", 0))
            )
            price = sorted_prices[0].get("sum", sorted_prices[0].get("price", 0))
            if isinstance(price, dict):
                price = price.get("value", 0) / 100.0
            old_price_raw = sorted_prices[-1].get(
                "sum", sorted_prices[-1].get("oldPrice", price)
            )
            if isinstance(old_price_raw, dict):
                old_price = old_price_raw.get("value", 0) / 100.0
            else:
                old_price = old_price_raw
    if price <= 0:
        return None

    has_promo = old_price > price
    promo_type = "discount" if has_promo else "standard"
    promo_condition = ""

    # Check for additional promo indicators
    if item.get("badges"):
        badge_texts = []
        for badge in item["badges"]:
            if isinstance(badge, dict):
                badge_text = badge.get("text", badge.get("title", ""))
                if badge_text:
                    badge_texts.append(str(badge_text))
        if badge_texts:
            promo_condition = " | ".join(badge_texts)

    if item.get("promos") or item.get("promotions") or item.get("discount"):
        has_promo = True
        promo_type = "discount"
        if not promo_condition:
            promo_condition = "Акция"

    # Извлечение картинки: новый API использует 'images' (массив),
    # старый — 'picture' (dict с uri/url)
    picture_url = None
    images_list = item.get("images")
    if isinstance(images_list, list) and images_list:
        # Новый формат: [{"default": "https://cdn.uzumtezkor.uz/..."}]
        picture_url = images_list[0].get("default") or images_list[0].get("url")

    if not picture_url:
        # Фоллбэк на старый формат
        picture_obj = item.get("picture") or item.get("image") or item.get("photo")
        if isinstance(picture_obj, dict):
            picture_url = picture_obj.get("uri") or picture_obj.get("url")
        elif isinstance(picture_obj, str):
            picture_url = picture_obj
        else:
            picture_url = item.get("imageUrl")

    return {
        "name": name,
        "price": float(price),
        "old_price": float(old_price),
        "has_promo": has_promo,
        "promo_type": promo_type,
        "promo_condition": promo_condition,
        "picture_url": picture_url,
    }


async def process_uzum_results(results: list[dict]) -> tuple[int, int, int]:
    """Save parsed Uzum Tezkor results to the database."""
    promos_count = 0
    errors_count = 0

    async with AsyncSessionLocal() as db:
        now = datetime.utcnow()
        parsed_promos = []
        for data in results:
            try:
                raw_name = data["name"]
                rest_name = normalize_restaurant_name(raw_name)
                mapped_category = map_restaurant_category(rest_name) or "Other"

                for item in data["items"]:
                    price = item["price"]
                    old_price = item["old_price"]
                    has_promo = item["has_promo"]

                    if has_promo and old_price > price > 0:
                        promos_count += 1
                        discount = round(((old_price - price) / old_price) * 100, 1)

                        promo = ParsedPromo(
                            timestamp=now,
                            aggregator_name="Uzum Tezkor",
                            restaurant_url=data.get("restaurant_url"),
                            competitor_name=data["name"],
                            picture_url=item.get("picture_url"),
                            item_category=mapped_category,
                            item_name=item["name"],
                            base_price=old_price,
                            promo_price=price,
                            discount_percent=discount,
                            promo_type=item.get("promo_type", "discount"),
                            promo_target="item_level",
                            promo_condition=item.get(
                                "promo_condition", "Скидка от заведения"
                            ),
                            position_in_list=data.get("position", 1),
                            is_in_carousel=False,
                            free_delivery_threshold=data["free_delivery_threshold"],
                            discount_threshold=None,
                            is_aggregator_funded=False,
                            delivery_fee=data["delivery_fee"],
                            service_fee=None,
                            min_order_value=data["min_order"],
                            delivery_time_min=data.get("delivery_time_min"),
                            delivery_time_max=data.get("delivery_time_max"),
                            search_query_used="Feed",
                            rating_score=data["rating"],
                            reviews_count=data["reviews"],
                        )
                        parsed_promos.append(promo)

            except Exception as e:
                errors_count += 1
                print(f"[Uzum Tezkor] DB error for {data.get('name', '?')}: {e}")

        if parsed_promos:
            db.add_all(parsed_promos)
            await db.commit()

    return len(results), promos_count, errors_count
