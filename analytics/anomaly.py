import pandas as pd
from typing import List, Dict, Any

class AnomalyDetector:
    def __init__(self, raw_promotions: List[Dict[str, Any]]):
        """
        Expects a joined list of dicts with keys: 
        restaurant_name, restaurant_reviews, promo_title, current_price, discount_percent
        """
        self.df = pd.DataFrame(raw_promotions)
        
    def detect_premium_brand_anomalies(self) -> pd.DataFrame:
        """
        Find cases where an identical dish is more expensive in one restaurant, 
        but that restaurant has significantly more reviews (loyalty / premium anomaly).
        """
        if self.df.empty or 'promo_title' not in self.df.columns:
            return pd.DataFrame()

        # Group by dish name (promo_title)
        anomalies = []
        
        for dish, group in self.df.groupby('promo_title'):
            if len(group) < 2:
                continue
                
            # Find the cheapest option
            cheapest = group.loc[group['current_price'].idxmin()]
            
            # Find options that are more expensive but have at least 20% MORE reviews
            more_expensive = group[group['current_price'] > cheapest['current_price']]
            for _, premium in more_expensive.iterrows():
                if premium['restaurant_reviews'] > (cheapest['restaurant_reviews'] * 1.2):
                    anomalies.append({
                        'Dish': dish,
                        'Cheapest_Rest': cheapest['restaurant_name'],
                        'Cheapest_Price': cheapest['current_price'],
                        'Cheapest_Reviews': cheapest['restaurant_reviews'],
                        'Premium_Rest': premium['restaurant_name'],
                        'Premium_Price': premium['current_price'],
                        'Premium_Reviews': premium['restaurant_reviews'],
                        'Price_Diff_%': round(((premium['current_price'] - cheapest['current_price']) / cheapest['current_price']) * 100, 1)
                    })
                    
        return pd.DataFrame(anomalies).sort_values(by='Price_Diff_%', ascending=False) if anomalies else pd.DataFrame()
