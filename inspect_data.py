"""Check Yandex promo category and Uzum vendors API."""

import json
import sys

sys.stdout.reconfigure(encoding="utf-8")

# YANDEX - Check the "Акции" category items
print("YANDEX - АКЦИИ CATEGORY ITEMS")
print("=" * 60)
with open("yandex_playwright_api_dump.json", "r", encoding="utf-8") as f:
    yd = json.load(f)

for item in yd:
    url = item.get("url", "")
    if "menu/retrieve" in url and "oqtepa_lavash__l4m92" in url:
        body = item.get("body", {})
        payload = body.get("payload", {})
        cats = payload.get("categories", [])
        for cat in cats:
            if "акц" in cat.get("name", "").lower():
                print(f"\nCategory: {cat.get('name')}")
                for it in cat.get("items", []):
                    print("\n  Full item:")
                    print(json.dumps(it, ensure_ascii=False, indent=4))

        # Also show first regular item for comparison
        for cat in cats:
            if cat.get("items") and "акц" not in cat.get("name", "").lower():
                print(f"\n\nSample regular item from '{cat.get('name')}':")
                print(json.dumps(cat["items"][0], ensure_ascii=False, indent=4))
                break
        break

# UZUM - Check the vendors API pattern
# The API is: /api/v1/vendors
# Also check /api/v1/selections (used for promo collections)
print("\n\n" + "=" * 60)
print("UZUM - VENDOR/SELECTIONS API PATTERNS")
print("=" * 60)

# Search in uzum_next_data.json for vendor slugs/IDs
with open("uzum_next_data.json", "r", encoding="utf-8") as f:
    uzum_data = json.load(f)

text = json.dumps(uzum_data, ensure_ascii=False)

# Find vendor-related API endpoints
import re

vendor_patterns = re.findall(r'/api/v\d/vendors[^"\'\\s]*', text)
print(f"Vendor API patterns: {sorted(set(vendor_patterns))[:10]}")

selection_patterns = re.findall(r'/api/v\d/selections[^"\'\\s]*', text)
print(f"Selection API patterns: {sorted(set(selection_patterns))[:10]}")

# Find vendor IDs (UUIDs)
uuid_pattern = re.findall(
    r'"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})"', text
)
unique_uuids = set(uuid_pattern)
print(f"\nTotal UUIDs found: {len(unique_uuids)}")
# Print first few as likely vendor IDs
for uid in list(unique_uuids)[:5]:
    print(f"  {uid}")

# Check props.pageProps structure from uzum_next_data
props = uzum_data.get("props", {}).get("pageProps", {})
initial = props.get("initialState", {})
print(f"\ninitialState keys: {list(initial.keys())}")

# The uzum_next_data.json was captured from a restaurant page
# Let's check if it has the restaurant data in a different location
rest = initial.get("restaurant", {})
if rest:
    print(f"restaurant keys: {list(rest.keys())}")
    if "data" in rest:
        rd = rest["data"]
        if isinstance(rd, dict):
            print(f"restaurant.data keys: {list(rd.keys())[:20]}")
            cats = rd.get("categories", [])
            if cats:
                print(f"  Categories: {len(cats)}")
                for c in cats[:2]:
                    items = c.get("items", [])
                    print(f"  Category: {c.get('title')}, {len(items)} items")
                    if items:
                        it = items[0]
                        print(f"    First item: {it.get('name')}")
                        print(f"    Item keys: {sorted(it.keys())}")
                        prices = it.get("prices", [])
                        if prices:
                            print(
                                f"    prices[0]: {json.dumps(prices[0], ensure_ascii=False)}"
                            )
                        # Check for promo fields
                        for pk in [
                            "promos",
                            "promo",
                            "badges",
                            "labels",
                            "discount",
                            "oldPrice",
                            "specialOffer",
                            "availablePromotions",
                        ]:
                            if pk in it:
                                print(
                                    f"    {pk}: {json.dumps(it[pk], ensure_ascii=False)[:200]}"
                                )
            else:
                print("  No categories!")
                # Maybe the restaurant data is loaded via API
                print("  (Data is loaded via client-side API call)")
