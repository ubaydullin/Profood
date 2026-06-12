from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Restaurant(Base):
    __tablename__ = 'restaurants'
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True) # 'Uzum Tezkor' or 'Yandex Eda'
    name = Column(String, index=True)
    category = Column(String, default="Uncategorized")
    
    # Social Proof
    rating_score = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0)
    
    # Pricing & Cart Metrics
    delivery_fee = Column(Float, nullable=True)
    service_fee = Column(Float, nullable=True)
    min_order_value = Column(Float, nullable=True)
    delivery_time_min = Column(Integer, nullable=True)
    delivery_time_max = Column(Integer, nullable=True)
    free_delivery_threshold = Column(Float, nullable=True)
    
    # Visibility Metrics (last known)
    position_in_list = Column(Integer, nullable=True)
    is_in_carousel = Column(Boolean, default=False)
    search_query_used = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    promotions = relationship("Promotion", back_populates="restaurant")

class Promotion(Base):
    __tablename__ = 'promotions'
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'))
    title = Column(String)
    description = Column(String, nullable=True)
    
    original_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    
    # Promo Constraints
    promo_type = Column(String) # 'discount', 'free_delivery', '1+1'
    promo_target = Column(String, default="item_level") # 'item_level', 'cart_level', 'delivery'
    promo_condition = Column(String, nullable=True) # e.g. 'orders over 100000'
    discount_threshold = Column(Float, nullable=True)
    is_aggregator_funded = Column(Boolean, default=False)
    
    is_active = Column(Boolean, default=True)
    snapshot_at = Column(DateTime, default=datetime.utcnow)
    
    restaurant = relationship("Restaurant", back_populates="promotions")
