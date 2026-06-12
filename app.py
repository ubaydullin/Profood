import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from sqlalchemy import create_engine
import os

from analytics.category_mapper import map_restaurant_category

st.set_page_config(page_title="SaleScrap - Конкурентная Разведка", layout="wide")

# --- Dark Glassmorphism CSS ---
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;700&display=swap');
    
    .stApp {
        background-color: #0F172A;
        color: #F8FAFC;
        font-family: 'Inter', sans-serif;
    }
    
    .glass-card {
        background: rgba(30, 41, 59, 0.7);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 12px;
        padding: 20px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        margin-bottom: 20px;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading ---
@st.cache_data(ttl=60)
def load_data():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'salescrap.db'))
    if not os.path.exists(db_path):
        return pd.DataFrame(), pd.DataFrame()
        
    engine = create_engine(f"sqlite:///{db_path}")
    
    # 1. Load active promotions
    query_promos = """
    SELECT 
        p.first_seen_at as timestamp,
        r.name as competitor_name,
        r.category as restaurant_category,
        p.title as item_name,
        p.original_price as base_price,
        p.current_price as promo_price,
        p.discount_percent,
        r.platform
    FROM promotions p
    JOIN restaurants r ON p.restaurant_id = r.id
    WHERE p.is_active = 1
    """
    df_promos = pd.read_sql(query_promos, engine)
    
    # 2. Load latest full catalog (from PriceSnapshot)
    # We get the most recent price for each item across the market
    query_catalog = """
    SELECT 
        s.snapshot_at as timestamp,
        r.name as competitor_name,
        r.category as restaurant_category,
        s.item_name,
        s.price as current_price,
        s.old_price,
        s.is_discounted,
        r.platform
    FROM price_snapshots s
    JOIN restaurants r ON s.restaurant_id = r.id
    GROUP BY r.id, s.item_name
    HAVING max(s.snapshot_at)
    """
    df_catalog = pd.read_sql(query_catalog, engine)
    
    return df_promos, df_catalog

df_promos, df_catalog = load_data()

st.markdown("<h1>SaleScrap <span style='color: #38BDF8'>Intelligence</span></h1>", unsafe_allow_html=True)

if df_catalog.empty:
    st.warning("База данных пока пуста. Запустите парсер `uv run python main.py --scrape`.")
    st.stop()

# --- Modules ---
tab1, tab2, tab3 = st.tabs(["🔥 Топ активных скидок", "🔍 Поиск товаров (Весь рынок)", "📊 Обзор рынка (Категории)"])

with tab1:
    st.markdown("### 🔥 Самые агрессивные предложения на рынке")
    if not df_promos.empty:
        # Sort by discount percent descending
        top_promos = df_promos.sort_values(by='discount_percent', ascending=False).head(50)
        
        # Display as a dataframe
        st.dataframe(
            top_promos[['platform', 'competitor_name', 'item_name', 'base_price', 'promo_price', 'discount_percent']],
            column_config={
                "platform": "Агрегатор",
                "competitor_name": "Заведение",
                "item_name": "Товар",
                "base_price": st.column_config.NumberColumn("Старая цена", format="%d Сум"),
                "promo_price": st.column_config.NumberColumn("Новая цена", format="%d Сум"),
                "discount_percent": st.column_config.NumberColumn("Скидка", format="-%.1f%%")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Активных скидок не найдено.")

with tab2:
    st.markdown("### 🔍 Поиск конкретных позиций для сравнения цен")
    st.markdown("Введите название блюда (например, 'Бургер', 'Лаваш' или 'Плов'), чтобы посмотреть, сколько оно стоит у всех конкурентов.")
    
    search_query = st.text_input("Поиск по всему рынку:", value="")
    
    if search_query:
        # Filter catalog by search query
        results = df_catalog[df_catalog['item_name'].str.contains(search_query, case=False, na=False)]
        
        if not results.empty:
            st.success(f"Найдено {len(results)} совпадений.")
            
            # Scatter plot of prices for the searched item across competitors
            fig = px.scatter(
                results,
                x='competitor_name',
                y='current_price',
                color='is_discounted',
                color_discrete_map={True: '#EF4444', False: '#38BDF8'},
                hover_name='item_name',
                title=f"Разброс цен на '{search_query}' по рынку",
                labels={'competitor_name': 'Конкурент', 'current_price': 'Текущая цена (Сум)', 'is_discounted': 'По акции?'}
            )
            fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#F8FAFC')
            st.plotly_chart(fig, use_container_width=True)
            
            # Data table
            st.dataframe(
                results[['platform', 'competitor_name', 'item_name', 'current_price', 'is_discounted']].sort_values('current_price'),
                hide_index=True,
                use_container_width=True
            )
        else:
            st.warning("Ничего не найдено.")

with tab3:
    st.markdown("### 📊 Обзор рынка (Активность по категориям)")
    
    if not df_promos.empty:
        # Count promos by category
        promo_counts = df_promos.groupby('restaurant_category').size().reset_index(name='promo_count')
        
        fig_pie = px.pie(
            promo_counts,
            names='restaurant_category',
            values='promo_count',
            title="Распределение всех скидок по типам кухни",
            hole=0.4,
            color_discrete_sequence=px.colors.sequential.Teal
        )
        fig_pie.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#F8FAFC')
        st.plotly_chart(fig_pie, use_container_width=True)
        
        # Average discount by category
        avg_disc = df_promos.groupby('restaurant_category')['discount_percent'].mean().reset_index()
        fig_bar = px.bar(
            avg_disc,
            x='restaurant_category',
            y='discount_percent',
            title="Средняя глубина скидки по категориям",
            labels={'restaurant_category': 'Категория', 'discount_percent': 'Средняя скидка (%)'},
            color='discount_percent',
            color_continuous_scale="Reds"
        )
        fig_bar.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#F8FAFC')
        st.plotly_chart(fig_bar, use_container_width=True)
    else:
        st.info("Недостаточно данных для обзора рынка.")
