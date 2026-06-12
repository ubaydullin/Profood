from typing import Dict, List

# Simple mapping logic for Tashkent restaurants
CATEGORY_MAP: Dict[str, List[str]] = {
    "Fast Food": ["evos", "oqtepa lavash", "maxway", "kfc", "feedup", "loook", "bellissimo"],
    "National Cuisine": ["rayhon", "kamolon", "besh qozon", "milliy", "shashlik"],
    "Sushi & Pan-Asian": ["yapona mama", "sushi", "wasabi", "chopsticks"],
    "Pizza": ["bellissimo", "chopar", "dominos", "pizza"],
    "Coffee & Desserts": ["safia", "chaiqof", "b&b", "black bear", "pie republic"]
}

def map_restaurant_category(restaurant_name: str) -> str:
    """
    Returns a mapped category based on restaurant name keywords.
    """
    name_lower = restaurant_name.lower()
    
    for category, keywords in CATEGORY_MAP.items():
        if any(keyword in name_lower for keyword in keywords):
            return category
            
    return "Other"
