"""Uzum Tezkor catalog builder.

Automatically collects restaurant URLs from the Uzum Tezkor homepage
by intercepting API responses. Scrolls the page to trigger lazy loading
and captures all vendor/restaurant data.

Usage:
    uv run python -m scraper.uzum_catalog_builder
"""

import json
import re
import sys
from pathlib import Path

# Fix Windows console encoding for Cyrillic text
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from scraper.geo_rotator import get_random_point


def build_catalog() -> list[dict]:
    """Build the Uzum Tezkor restaurant catalog using Playwright.

    Opens the Uzum Tezkor homepage, sets a delivery address,
    scrolls to load all restaurants, and intercepts API responses
    to extract restaurant IDs and slugs.

    Returns:
        List of catalog entries with url, id, and name.
    """
    from playwright.sync_api import sync_playwright

    geo = get_random_point()
    print(
        f"[Uzum Catalog] Using geo: {geo['name']} "
        f"({geo['latitude']:.4f}, {geo['longitude']:.4f})"
    )

    captured_responses: list[dict] = []
    restaurant_ids: set[str] = set()
    restaurant_entries: list[dict] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            geolocation={
                "latitude": geo["latitude"],
                "longitude": geo["longitude"],
            },
            permissions=["geolocation"],
            locale="ru-RU",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/125.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        def handle_response(response):
            """Capture JSON responses containing vendor data."""
            try:
                content_type = response.headers.get("content-type", "")
                if "application/json" not in content_type:
                    return

                url = response.url
                skip = [
                    "metrics",
                    "log",
                    "analytics",
                    "growthbook",
                    "clickstream",
                    "event",
                    "decode-jwt",
                    "maps.yandex",
                    "kevel",
                    "zendesk",
                ]
                if any(pat in url for pat in skip):
                    return

                body = response.json()
                captured_responses.append(
                    {
                        "url": url,
                        "body": body,
                    }
                )
            except Exception:
                pass

        page.on("response", handle_response)

        # Navigate to the main page
        print("[Uzum Catalog] Navigating to homepage...")
        page.goto(
            "https://www.uzumtezkor.uz/ru", wait_until="networkidle", timeout=30000
        )
        page.wait_for_timeout(3000)

        # Try to set address / dismiss modal
        _try_set_address(page, geo)

        page.wait_for_timeout(3000)

        # Scroll to load all restaurants
        print("[Uzum Catalog] Scrolling to load all restaurants...")
        _scroll_page(page, scroll_steps=50)

        # Also visit promo selection pages to find restaurants with active promos
        promo_sections = [
            "https://www.uzumtezkor.uz/ru/restaurant/onePlusOne",
            "https://www.uzumtezkor.uz/ru/restaurant/deliveryPrice",
            "https://www.uzumtezkor.uz/ru/restaurant/deliveryTime",
            "https://www.uzumtezkor.uz/ru/restaurant/present",
            "https://www.uzumtezkor.uz/ru/restaurant/twoPlusOne",
        ]

        for promo_url in promo_sections:
            section_name = promo_url.split("/")[-1]
            print(f"[Uzum Catalog] Visiting promo section: {section_name}...")
            try:
                page.goto(promo_url, wait_until="networkidle", timeout=15000)
                page.wait_for_timeout(2000)
                _scroll_page(page, scroll_steps=10)
            except Exception as e:
                print(f"[Uzum Catalog] Error visiting {section_name}: {e}")

        browser.close()

    # Process all captured responses
    print(
        f"\n[Uzum Catalog] Processing {len(captured_responses)} captured responses..."
    )

    for resp in captured_responses:
        url = resp.get("url", "")
        body = resp.get("body", {})

        if not isinstance(body, dict):
            continue

        _extract_restaurants(body, url, restaurant_ids, restaurant_entries)

    # Also extract from page HTML source if available
    # (fallback for aliases found in HTML)

    print(f"\n[Uzum Catalog] Found {len(restaurant_entries)} unique restaurants.")

    # Save catalog
    output_path = Path(__file__).parent.parent / "uzum_catalog.json"

    # Create output as list of URL strings for backward compatibility
    catalog_urls = [entry["url"] for entry in restaurant_entries]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(catalog_urls, f, ensure_ascii=False, indent=2)

    print(f"[Uzum Catalog] Saved {len(catalog_urls)} restaurants to {output_path}")

    # Also save detailed catalog
    detailed_path = Path(__file__).parent.parent / "uzum_catalog_detailed.json"
    with open(detailed_path, "w", encoding="utf-8") as f:
        json.dump(restaurant_entries, f, ensure_ascii=False, indent=2)

    print(f"[Uzum Catalog] Detailed catalog saved to {detailed_path}")

    return restaurant_entries


def _extract_restaurants(
    body: dict,
    url: str,
    seen_ids: set[str],
    entries: list[dict],
) -> None:
    """Extract restaurant entries from a captured API response.

    Looks for vendor/restaurant data in various response formats.

    Args:
        body: Parsed JSON response body.
        url: URL of the response.
        seen_ids: Set of already-seen restaurant IDs.
        entries: List to append new entries to.
    """
    # Look for vendor lists in different response structures
    vendors: list[dict] = []

    # Direct array of vendors
    if isinstance(body, dict):
        for key in ["vendors", "vendorList", "data", "items", "restaurants"]:
            val = body.get(key)
            if isinstance(val, list):
                vendors.extend(val)
            elif isinstance(val, dict) and "items" in val:
                vendors.extend(val.get("items", []))

    # Check nested structures
    if not vendors:
        text = json.dumps(body, ensure_ascii=False)
        # Find UUID-like IDs that look like vendor references
        uuid_matches = re.findall(
            r'"id"\s*:\s*"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"',
            text,
        )
        alias_matches = re.findall(r'"alias"\s*:\s*"([^"]+)"', text)
        slug_matches = re.findall(r'"slug"\s*:\s*"([^"]+)"', text)

        # For standalone IDs, create minimal entries
        for uid in uuid_matches:
            if uid not in seen_ids and len(uid) > 10:
                # Verify it's likely a vendor ID by context
                idx = text.find(uid)
                context = text[max(0, idx - 100) : idx + 100]
                if any(
                    kw in context.lower()
                    for kw in ["vendor", "restaurant", "title", "alias", "category"]
                ):
                    seen_ids.add(uid)
                    entries.append(
                        {
                            "url": f"https://www.uzumtezkor.uz/ru/restaurants/{uid}",
                            "id": uid,
                            "name": "",
                            "source": url[:100],
                        }
                    )

        for alias in alias_matches + slug_matches:
            if alias not in seen_ids and len(alias) > 2 and "/" not in alias:
                seen_ids.add(alias)
                entries.append(
                    {
                        "url": f"https://www.uzumtezkor.uz/ru/restaurants/{alias}",
                        "id": alias,
                        "name": alias,
                        "source": url[:100],
                    }
                )
        return

    for vendor in vendors:
        if not isinstance(vendor, dict):
            continue

        vendor_id = (
            vendor.get("id")
            or vendor.get("uuid")
            or vendor.get("alias")
            or vendor.get("slug")
        )
        if not vendor_id or str(vendor_id) in seen_ids:
            continue

        seen_ids.add(str(vendor_id))
        name = vendor.get("title") or vendor.get("name") or ""

        entries.append(
            {
                "url": f"https://www.uzumtezkor.uz/ru/restaurants/{vendor_id}",
                "id": str(vendor_id),
                "name": name,
                "source": url[:100],
            }
        )


def _try_set_address(page, geo: dict) -> None:
    """Try to set the delivery address on the Uzum Tezkor homepage.

    Attempts multiple strategies:
    1. Click "Определить" (detect location) button
    2. Click through address modal

    Args:
        page: Playwright page object.
        geo: GeoPoint dict with latitude/longitude.
    """
    try:
        # Strategy 1: Click common address-related buttons
        button_texts = [
            "Определить",
            "Текущее местоположение",
            "Подтвердить",
            "Сохранить",
            "OK",
        ]
        for text in button_texts:
            try:
                btn = page.locator(f'button:has-text("{text}")').first
                if btn.is_visible(timeout=2000):
                    btn.click()
                    page.wait_for_timeout(1000)
                    print(f"[Uzum Catalog] Clicked '{text}' button")
                    return
            except Exception:
                continue

        # Strategy 2: Close any modal overlay
        try:
            close_btn = page.locator('[class*="close"], [class*="dismiss"]').first
            if close_btn.is_visible(timeout=2000):
                close_btn.click()
                page.wait_for_timeout(1000)
                print("[Uzum Catalog] Closed modal overlay")
                return
        except Exception:
            pass

        print("[Uzum Catalog] No address picker found, continuing...")

    except Exception as e:
        print(f"[Uzum Catalog] Address setup error: {e}")


def _scroll_page(page, scroll_steps: int = 50) -> None:
    """Scroll the page down to trigger lazy loading of restaurants.

    Args:
        page: Playwright page object.
        scroll_steps: Number of scroll increments.
    """
    for i in range(scroll_steps):
        page.evaluate("window.scrollBy(0, 1500)")
        page.wait_for_timeout(500)
        if (i + 1) % 10 == 0:
            print(f"[Uzum Catalog] Scrolled step {i + 1}/{scroll_steps}")


if __name__ == "__main__":
    build_catalog()
