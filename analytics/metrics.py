import pandas as pd
from typing import List, Dict, Any

class PromoAnalytics:
    def __init__(self, raw_data: List[Dict[str, Any]]):
        """
        Expects raw_data from the database as a list of dictionaries.
        """
        self.df = pd.DataFrame(raw_data)
        
    def get_market_share(self) -> pd.DataFrame:
        """
        Calculate total active promotions grouped by platform.
        """
        if self.df.empty:
            return pd.DataFrame()
            
        share = self.df.groupby('platform')['id'].count().reset_index()
        share.columns = ['Platform', 'Promo Count']
        return share
        
    def get_average_discount_by_category(self) -> pd.DataFrame:
        """
        Calculate the average discount percentage by restaurant category.
        """
        if self.df.empty or 'discount_percent' not in self.df.columns:
            return pd.DataFrame()
            
        avg_discount = self.df.groupby('category')['discount_percent'].mean().reset_index()
        avg_discount.columns = ['Category', 'Average Discount (%)']
        return avg_discount.sort_values(by='Average Discount (%)', ascending=False)
