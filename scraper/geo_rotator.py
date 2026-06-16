"""Geo-coordinate rotator for anti-bot detection.

Provides randomized delivery addresses across Tashkent districts
to mimic real user behavior and avoid bot fingerprinting.
"""

import random
from typing import TypedDict


class GeoPoint(TypedDict):
    """A geographic point with name for logging."""

    latitude: float
    longitude: float
    name: str


# Residential areas across all major Tashkent districts
TASHKENT_POINTS: list[GeoPoint] = [
    # Yunusabad
    {"latitude": 41.3547, "longitude": 69.2856, "name": "Юнусабад, 11-квартал"},
    {"latitude": 41.3632, "longitude": 69.2741, "name": "Юнусабад, 19-квартал"},
    # Mirzo Ulugbek
    {
        "latitude": 41.3389,
        "longitude": 69.3342,
        "name": "Мирзо-Улугбек, Буюк Ипак Йули",
    },
    {"latitude": 41.3281, "longitude": 69.3517, "name": "Мирзо-Улугбек, Катартал"},
    # Chilanzar
    {"latitude": 41.2826, "longitude": 69.1981, "name": "Чиланзар, 9-квартал"},
    {"latitude": 41.2753, "longitude": 69.2134, "name": "Чиланзар, 19-квартал"},
    # Shaykhantakhur
    {"latitude": 41.3283, "longitude": 69.2487, "name": "Шайхантаур, Навои"},
    {"latitude": 41.3191, "longitude": 69.2536, "name": "Шайхантаур, Амир Темур"},
    # Yakkasaray
    {"latitude": 41.2995, "longitude": 69.2790, "name": "Яккасарай, Бабура"},
    {"latitude": 41.2934, "longitude": 69.2645, "name": "Яккасарай, Шота Руставели"},
    # Sergeli
    {"latitude": 41.2281, "longitude": 69.2183, "name": "Сергели, 7-сектор"},
    {"latitude": 41.2345, "longitude": 69.2356, "name": "Сергели, 5-сектор"},
    # Mirabad
    {"latitude": 41.3062, "longitude": 69.2679, "name": "Мирабад, Мирабад"},
    {"latitude": 41.3115, "longitude": 69.2797, "name": "Мирабад, Новза"},
    # Uchtepa
    {"latitude": 41.3043, "longitude": 69.2154, "name": "Учтепа, Кичик Халка Йули"},
    # Bektemir
    {"latitude": 41.2421, "longitude": 69.3345, "name": "Бектемир, Бектемир"},
    # Olmazor
    {"latitude": 41.3411, "longitude": 69.2134, "name": "Алмазар, ТТЗ"},
]


def get_random_point() -> GeoPoint:
    """Return a random Tashkent geo point.

    Returns:
        A randomly selected GeoPoint from residential areas in Tashkent,
        with slight coordinate jitter (±200m) for extra uniqueness.
    """
    point = random.choice(TASHKENT_POINTS).copy()
    # Add ±0.002 degrees (~200m) jitter to avoid exact-match detection
    point["latitude"] += random.uniform(-0.002, 0.002)
    point["longitude"] += random.uniform(-0.002, 0.002)
    return point


def get_fixed_point() -> GeoPoint:
    """Return the central Tashkent point (Amir Temur Square area).

    Returns:
        A fixed GeoPoint near the center of Tashkent.
    """
    return {
        "latitude": 41.3115,
        "longitude": 69.2797,
        "name": "Ташкент, центр",
    }
