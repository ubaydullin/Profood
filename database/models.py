from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import declarative_base, relationship
from datetime import datetime

Base = declarative_base()

class Restaurant(Base):
    __tablename__ = 'restaurants'
    
    id = Column(Integer, primary_key=True, index=True)
    platform = Column(String, index=True) # 'uzum' or 'yandex'
    name = Column(String, index=True)
    category = Column(String, default="Uncategorized")
    rating = Column(Float, nullable=True)
    reviews_count = Column(Integer, default=0) # Added for anomaly detection
    created_at = Column(DateTime, default=datetime.utcnow)
    
    promotions = relationship("Promotion", back_populates="restaurant")

class Promotion(Base):
    __tablename__ = 'promotions'
    
    id = Column(Integer, primary_key=True, index=True)
    restaurant_id = Column(Integer, ForeignKey('restaurants.id'))
    title = Column(String) # Dish or Promo Name e.g. "Lavash Meat"
    description = Column(String, nullable=True)
    
    original_price = Column(Float, nullable=True)
    current_price = Column(Float, nullable=True)
    discount_percent = Column(Float, nullable=True)
    
    promo_type = Column(String) # e.g. 'discount', 'free_delivery'
    is_active = Column(Boolean, default=True)
    snapshot_at = Column(DateTime, default=datetime.utcnow)
    
    restaurant = relationship("Restaurant", back_populates="promotions")
