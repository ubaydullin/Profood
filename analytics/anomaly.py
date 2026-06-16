import pandas as pd
from typing import List, Dict, Any


class AnomalyDetector:
    def __init__(self, raw_promotions: List[Dict[str, Any]]):
        """
        Expects a joined list of dicts with keys:
        competitor_name, reviews_count, item_name, final_price, discount_percent
        """
        self.df = pd.DataFrame(raw_promotions)

    def detect_premium_brand_anomalies(self) -> pd.DataFrame:
        """
        Find cases where an identical dish is more expensive in one restaurant,
        but that restaurant has significantly more reviews (loyalty / premium anomaly).
        """
        if self.df.empty or "item_name" not in self.df.columns:
            return pd.DataFrame()

        # Group by dish name (item_name)
        anomalies = []

        for dish, group in self.df.groupby("item_name"):
            if len(group) < 2:
                continue

            # Find the cheapest option
            cheapest = group.loc[group["final_price"].idxmin()]

            # Find options that are more expensive but have at least 20% MORE reviews
            more_expensive = group[group["final_price"] > cheapest["final_price"]]
            for _, premium in more_expensive.iterrows():
                if premium["reviews_count"] > (cheapest["reviews_count"] * 1.2):
                    anomalies.append(
                        {
                            "Dish": dish,
                            "Cheapest_Rest": cheapest["competitor_name"],
                            "Cheapest_Price": cheapest["final_price"],
                            "Cheapest_Reviews": cheapest["reviews_count"],
                            "Premium_Rest": premium["competitor_name"],
                            "Premium_Price": premium["final_price"],
                            "Premium_Reviews": premium["reviews_count"],
                            "Price_Diff_%": round(
                                (
                                    (premium["final_price"] - cheapest["final_price"])
                                    / cheapest["final_price"]
                                )
                                * 100,
                                1,
                            ),
                        }
                    )

        return (
            pd.DataFrame(anomalies).sort_values(by="Price_Diff_%", ascending=False)
            if anomalies
            else pd.DataFrame()
        )
