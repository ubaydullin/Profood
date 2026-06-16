from datetime import datetime
from typing import Optional

from sqlalchemy import Integer, String, Float, Boolean, DateTime
from sqlalchemy.orm import declarative_base, Mapped, mapped_column

Base = declarative_base()

class ParsedPromo(Base):
    """
    Единая плоская таблица для хранения результатов парсинга агрегаторов доставки еды,
    содержащая всю информацию о заведении, конкретном товаре и условиях акции.
    """
    __tablename__ = "parsed_promos"

    # БЛОК 1: Идентификация и Время
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    aggregator_name: Mapped[str] = mapped_column(String, index=True)
    competitor_name: Mapped[str] = mapped_column(String, index=True)

    # БЛОК 2: Товар и Ценообразование
    item_category: Mapped[str] = mapped_column(String, default="Uncategorized")
    item_name: Mapped[str] = mapped_column(String, index=True)
    base_price: Mapped[float] = mapped_column(Float)
    promo_price: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    discount_percent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # БЛОК 3: Условия Акций (Promo Constraints)
    promo_type: Mapped[str] = mapped_column(String, default="standard")
    promo_target: Mapped[str] = mapped_column(String, default="item_level")
    free_delivery_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    discount_threshold: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    promo_condition: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    is_aggregator_funded: Mapped[bool] = mapped_column(Boolean, default=False)

    # БЛОК 4: Доставка и Видимость (Delivery & Visibility)
    delivery_fee: Mapped[float] = mapped_column(Float)
    service_fee: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    min_order_value: Mapped[float] = mapped_column(Float)
    delivery_time_min: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    delivery_time_max: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    position_in_list: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_in_carousel: Mapped[bool] = mapped_column(Boolean, default=False)
    search_query_used: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    rating_score: Mapped[float] = mapped_column(Float, default=4.5)
    reviews_count: Mapped[int] = mapped_column(Integer, default=0)
