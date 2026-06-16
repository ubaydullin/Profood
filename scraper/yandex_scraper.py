"""Yandex Eda scraper.

Fetches restaurant menus via the Yandex Eda public API and extracts
promotions (promoPrice, promoTypes, badges) and regular discounts.
Uses geo-rotation across Tashkent addresses for anti-bot protection.
"""

import sys

if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import asyncio
import json
import os
import re
from datetime import datetime

from database.db import AsyncSessionLocal
from database.models import ParsedPromo
from scraper.api_client import AsyncAPIClient
from scraper.geo_rotator import get_random_point


async def async_scrape_yandex() -> list[dict]:
    """Fetch and parse menu data from all restaurants in yandex_catalog.json.

    Returns:
        List of dicts with restaurant name, metadata, and items with prices.
    """
    print("[Yandex Eda] Starting scrape from catalog API...")
    catalog_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "yandex_catalog.json"
    )

    if not os.path.exists(catalog_path):
        print(f"[Yandex Eda] Catalog not found: {catalog_path}")
        return []

    with open(catalog_path, "r", encoding="utf-8") as f:
        links = json.load(f)

    print(f"[Yandex Eda] Loaded {len(links)} restaurants from catalog.")

    results: list[dict] = []

    # Use a random Tashkent geo point for this session
    geo = get_random_point()
    print(
        f"[Yandex Eda] Using geo point: {geo['name']} "
        f"({geo['latitude']:.4f}, {geo['longitude']:.4f})"
    )

    client = AsyncAPIClient(
        base_url="https://eats.yandex.com/api/v2/menu/retrieve",
        custom_headers={
            "accept": "application/json",
            "referer": "https://eats.yandex.com/uz/r",
        },
    )

    # Расширенный фильтр мусора (включая кириллицу)
    RETAIL_TRASH = {
        "makro",
        "макро",
        "zoo planeta",
        "зоо",
        "korzinka go",
        "korzinka",
        "корзинка",
        "the loaf",
        "apteka",
        "аптека",
        "pharmacy",
        "texnomart",
        "baraka",
        "барака",
    }

    for idx, url in enumerate(links):
        try:
            slug_match = re.search(r"placeSlug=([^&]+)", url)
            if not slug_match:
                slug = url.split("?")[0].split("/")[-1]
            else:
                slug = slug_match.group(1)

            rest_name = url.split("?")[0].split("/")[-1]
            print(f"[Yandex Eda] Fetching API for {rest_name}...")

            params = {
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
                "autoTranslate": "false",
            }
            data = await client.get(slug, params=params)

            if not data or "payload" not in data:
                print(f"[Yandex Eda] Failed to get valid data for {slug}")
                continue

            place = data["payload"].get("place", {})
            rest_name = place.get("name", rest_name)

            # --- ИЗВЛЕЧЕНИЕ РЕАЛЬНЫХ МЕТРИК РЕСТОРАНА ---
            # Рейтинг
            raw_rating = place.get("rating", None)
            if isinstance(raw_rating, dict):
                raw_rating = raw_rating.get("score", None)
            rating = float(raw_rating) if raw_rating is not None else None

            # Отзывы
            reviews = place.get("ratingCount", None)

            # Доставка и пороги
            delivery_data = place.get("delivery", {})
            delivery_fee = 0.0
            free_delivery_threshold = None

            if "price" in delivery_data:
                delivery_fee = float(delivery_data["price"].get("value", 0))

            if "conditions" in delivery_data:
                for cond in delivery_data["conditions"]:
                    if cond.get("deliveryCost", {}).get("value") == 0:
                        free_delivery_threshold = float(
                            cond.get("orderMinPrice", {}).get("value", 0)
                        )
            # ---------------------------------------------

            # Пропуск ритейла
            if any(trash in rest_name.lower() for trash in RETAIL_TRASH):
                print(f"[Yandex Eda] Skipping retail/trash: {rest_name}")
                continue

            items: list[dict] = []
            categories = data["payload"].get("categories", [])
            for cat in categories:
                cat_name = cat.get("name", "")
                cat_items = cat.get("items", [])
                for item in cat_items:
                    parsed = _parse_yandex_item(item, cat_name)
                    if parsed:
                        items.append(parsed)

            if items:
                promo_count = sum(1 for it in items if it["has_promo"])
                results.append(
                    {
                        "name": rest_name.strip().title(),
                        "restaurant_url": url,
                        "position": idx + 1,
                        "rating": rating,
                        "reviews": reviews,
                        "delivery_fee": delivery_fee,
                        "min_order": 0,
                        "free_delivery_threshold": free_delivery_threshold,
                        "items": items,
                    }
                )
                print(
                    f"[Yandex Eda] Scraped {rest_name}: "
                    f"{len(items)} items, {promo_count} promos"
                )
            else:
                print(f"[Yandex Eda] No items found for {rest_name}")

            # Small delay between requests to avoid rate limiting
            await asyncio.sleep(0.3)

        except Exception as e:
            print(f"[Yandex Eda] Error parsing {url}: {e}")

    await client.close()
    return results


def _parse_yandex_item(item: dict, category_name: str) -> dict | None:
    """Parse a single Yandex Eda menu item, extracting promo info.

    Yandex Eda uses three discount mechanisms:
    1. promoPrice / decimalPromoPrice — акционная цена (e.g. "Скидка деньгами")
    2. oldPrice / decimalOldPrice — зачёркнутая старая цена
    3. badges with type "promo" — визуальные бейджи акции

    Args:
        item: Raw item dict from the Yandex API.
        category_name: Name of the parent category.

    Returns:
        Parsed item dict with price, promo info, or None if invalid.
    """
    name = item.get("name", "Unknown")

    # Base price (always present)
    price_val = item.get("decimalPrice") or item.get("price") or 0
    try:
        price = float(price_val)
    except ValueError, TypeError:
        price = 0

    if price <= 0:
        return None

    # --- Detect promo/discount ---
    has_promo = False
    original_price = price
    current_price = price
    promo_type = "standard"
    promo_condition = ""

    # Mechanism 1: promoPrice (Yandex-specific promo pricing)
    promo_price_val = item.get("decimalPromoPrice") or item.get("promoPrice")
    if promo_price_val is not None:
        try:
            promo_price = float(promo_price_val)
            if 0 < promo_price < price:
                has_promo = True
                original_price = price
                current_price = promo_price
        except ValueError, TypeError:
            pass

    # Mechanism 2: oldPrice (classic strikethrough discount)
    if not has_promo:
        old_price_val = item.get("decimalOldPrice") or item.get("oldPrice")
        if old_price_val is not None:
            try:
                old_price = float(old_price_val)
                if old_price > price:
                    has_promo = True
                    original_price = old_price
                    current_price = price
            except ValueError, TypeError:
                pass

    # Extract promo type from promoTypes array
    promo_types_list = item.get("promoTypes", [])
    if promo_types_list:
        promo_type_names = [pt.get("name", "") for pt in promo_types_list]
        promo_type = "discount"
        promo_condition = "; ".join(
            promo_types_list[0].get("name", "") for _ in [0]
        )  # First promo type name
        if promo_type_names:
            promo_condition = promo_type_names[0]

    # Extract badge info for additional context
    badges = item.get("badges", [])
    badge_texts: list[str] = []
    for badge in badges:
        text_obj = badge.get("text", {})
        if isinstance(text_obj, dict):
            badge_text = text_obj.get("value", "")
            if badge_text:
                badge_texts.append(badge_text)

    # Determine promo type from badges
    if badge_texts and not promo_condition:
        promo_condition = " | ".join(badge_texts)

    # Check for promo items count limit
    promo_limit = item.get("promo_items_count_limit")
    if promo_limit:
        promo_condition += f" (лимит: {promo_limit} шт)"

    # Category-level promo detection (items in "Акции" category)
    is_in_promo_category = "акци" in category_name.lower()
    if is_in_promo_category and not has_promo:
        # Item is in promo category but has no explicit price discount
        has_promo = True
        promo_type = "promo_set"
        if not promo_condition:
            promo_condition = f"Категория: {category_name}"

    return {
        "name": name,
        "price": current_price,
        "old_price": original_price,
        "has_promo": has_promo,
        "promo_type": promo_type,
        "promo_condition": promo_condition,
        "badge_texts": badge_texts,
        "category": category_name,
        "available": item.get("available", True),
    }


async def process_yandex_results(results: list[dict]) -> tuple[int, int, int]:
    promos_count = 0
    errors_count = 0
    now = datetime.utcnow()  # Исправлено: добавлено время парсинга

    async with AsyncSessionLocal() as db:
        for data in results:
            try:
                parsed_promos = []
                for item in data["items"]:
                    price = item["price"]
                    old_price = item["old_price"]
                    has_promo = item["has_promo"]

                    if has_promo and old_price > price > 0:
                        promos_count += 1
                        discount = round(((old_price - price) / old_price) * 100, 1)
                        promo_type = item.get("promo_type", "discount")
                    elif has_promo and old_price == price:
                        promos_count += 1
                        discount = 0.0
                        promo_type = item.get("promo_type", "promo_set")
                    else:
                        discount = 0.0
                        promo_type = "standard"

                    promo = ParsedPromo(
                        timestamp=now,
                        aggregator_name="Yandex Eda",
                        restaurant_url=data.get("restaurant_url"),
                        competitor_name=data["name"],
                        item_category=item.get("category", "Other"),
                        item_name=item["name"],
                        base_price=old_price,
                        promo_price=price if has_promo else None,
                        discount_percent=discount if has_promo else None,
                        promo_type=promo_type,
                        promo_target="item_level",
                        promo_condition=item.get(
                            "promo_condition", "Скидка от заведения"
                        )
                        if has_promo
                        else None,
                        free_delivery_threshold=data["free_delivery_threshold"],
                        discount_threshold=None,
                        is_aggregator_funded=False,
                        delivery_fee=data["delivery_fee"],
                        service_fee=1000,
                        min_order_value=data["min_order"],
                        delivery_time_min=20,
                        delivery_time_max=45,
                        position_in_list=data.get("position", 1),
                        is_in_carousel=False,
                        search_query_used="Feed",
                        rating_score=data["rating"],
                        reviews_count=data["reviews"],
                    )
                    parsed_promos.append(promo)

                db.add_all(parsed_promos)

            except Exception as e:
                errors_count += 1
                print(f"[Yandex Eda] DB error for {data.get('name', '?')}: {e}")

        await db.commit()

    return len(results), promos_count, errors_count


async def scrape_yandex() -> tuple[int, int, int]:
    """Main entry point for the Yandex Eda scraper.

    Returns:
        Tuple of (restaurants_count, promos_count, errors_count).
    """
    try:
        results = await async_scrape_yandex()
        if not results:
            return 0, 0, 1
        stats = await process_yandex_results(results)
        print("[Yandex] Completed scrape.")
        return stats
    except Exception as e:
        print(f"[Yandex] Scrape failed: {e}")
        return 0, 0, 1
