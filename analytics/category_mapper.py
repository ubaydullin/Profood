from typing import Dict, List, Optional
import re

# Simple mapping logic for Tashkent restaurants
CATEGORY_MAP: Dict[str, List[str]] = {
    "Fast Food": [
        "evos",
        "oqtepa lavash",
        "maxway",
        "kfc",
        "feedup",
        "loook",
        "bellissimo",
        "burger",
    ],
    "National Cuisine": [
        "rayhon",
        "kamolon",
        "besh qozon",
        "milliy",
        "shashlik",
        "plov",
        "somsa",
    ],
    "Sushi & Pan-Asian": ["yapona mama", "sushi", "wasabi", "chopsticks", "wok"],
    "Pizza": ["bellissimo", "chopar", "dominos", "pizza", "papa johns"],
    "Coffee & Desserts": [
        "safia",
        "chaiqof",
        "b&b",
        "black bear",
        "pie republic",
        "cake",
        "coffee",
    ],
}

# Ignore list for non-food stores
IGNORE_KEYWORDS: List[str] = [
    "аптека",
    "apteka",
    "pharmacy",
    "dorixona",
    "цветы",
    "flowers",
    "gullar",
    "cvety",
    "зоомагазин",
    "zoo",
    "pet shop",
    "супермаркет",
    "market",
    "korzinka",
    "makro",
    "heves",
    "косметика",
    "cosmetics",
]


def normalize_restaurant_name(restaurant_name: str) -> str:
    """
    Strips branch information to deduplicate chains.
    e.g., 'Oqtepa Lavash (Ц-1)' -> 'Oqtepa Lavash'
    """
    # Remove text in parentheses
    name = re.sub(r"\(.*?\)", "", restaurant_name)
    # Remove common branch keywords
    name = re.sub(
        r"(?i)\b(филиал|улица|мкр|район|yunusobod|chilonzor|yashnobod|tashkent)\b.*",
        "",
        name,
    )
    return name.strip()


def map_restaurant_category(restaurant_name: str) -> Optional[str]:
    """
    Returns a mapped category based on restaurant name keywords.
    Returns None if the store is in the ignore list.
    """
    name_lower = restaurant_name.lower()

    # Smart filtering: Drop non-food businesses
    if any(keyword in name_lower for keyword in IGNORE_KEYWORDS):
        return None

    for category, keywords in CATEGORY_MAP.items():
        if any(keyword in name_lower for keyword in keywords):
            return category

    return "Other"
