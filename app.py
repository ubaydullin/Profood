import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
import os
from datetime import datetime, timedelta

from analytics.category_mapper import map_restaurant_category

st.set_page_config(page_title="Market Promo Tracker", layout="wide", initial_sidebar_state="expanded")

# --- Corporate Colors ---
OUR_BRANDS = ["Mazzali", "Шеф Burger", "Chef Burger", "Mazzali (Ex. Chef Burger)"]
COLOR_OURS = "rgb(3, 92, 87)"       # Corporate green/teal
COLOR_COMPETITOR = "rgb(156, 163, 175)" # Grey
COLOR_COMPETITOR_AGGRESSIVE = "rgb(239, 68, 68)" # Red

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
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #38BDF8;
        margin-bottom: 4px;
    }
    
    .metric-label {
        font-size: 0.85rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        font-weight: 600;
    }
    
    .metric-subtext {
        font-size: 0.8rem;
        color: #EF4444;
        font-weight: 500;
        margin-top: 4px;
    }
</style>
""", unsafe_allow_html=True)

# --- Data Loading & Mocking ---
@st.cache_data(ttl=300)
def load_data():
    db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'salescrap.db'))
    if not os.path.exists(db_path):
        # Fallback empty dataframe if no DB yet
        return pd.DataFrame(columns=[
            'timestamp', 'competitor_name', 'item_category', 'base_price', 'promo_price', 
            'promo_type', 'aggregator_rank', 'our_sales_volume', 'is_our_brand', 'platform'
        ])
        
    engine = create_engine(f"sqlite:///{db_path}")
    
    query = """
    SELECT 
        p.snapshot_at as timestamp,
        r.name as competitor_name,
        r.category as restaurant_category,
        p.title as item_name,
        p.original_price as base_price,
        p.current_price as promo_price,
        p.discount_percent,
        p.promo_type,
        r.platform
    FROM promotions p
    JOIN restaurants r ON p.restaurant_id = r.id
    WHERE p.is_active = 1
    """
    df = pd.read_sql(query, engine)
    
    if df.empty:
        return pd.DataFrame(columns=[
            'timestamp', 'competitor_name', 'item_category', 'base_price', 'promo_price', 
            'promo_type', 'aggregator_rank', 'our_sales_volume', 'is_our_brand', 'platform', 'item_name'
        ])
    
    # Process & Mock missing fields
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Fill prices where missing
    df['base_price'] = df['base_price'].fillna(df['promo_price'])
    
    # Item category (mocking from title or rest category)
    df['item_category'] = df['item_name'].apply(map_restaurant_category)
    
    # Is our brand?
    df['is_our_brand'] = df['competitor_name'].apply(lambda x: any(brand.lower() in str(x).lower() for brand in OUR_BRANDS))
    
    # Calculate discount depth
    df['discount_depth'] = np.where(
        df['base_price'] > df['promo_price'], 
        ((df['base_price'] - df['promo_price']) / df['base_price'] * 100).round(1),
        0
    )
    
    # MOCK: aggregator_rank (1 to 50)
    # Give our brands worse rank if they have no promo, and give aggressive promos better rank
    np.random.seed(42)
    base_rank = np.random.randint(10, 40, size=len(df))
    promo_boost = (df['discount_depth'] > 10).astype(int) * np.random.randint(5, 15, size=len(df))
    df['aggregator_rank'] = np.clip(base_rank - promo_boost, 1, 50)
    
    # MOCK: our_sales_volume (Time Series)
    # We will generate this separately for the timeline, but we can assign a random metric per row
    df['our_sales_volume'] = np.random.randint(10, 100, size=len(df))
    
    return df

df = load_data()

# --- Title ---
st.markdown("<h1>Market Promo Tracker <span style='color: #38BDF8'>Mazzali</span></h1>", unsafe_allow_html=True)

if df.empty:
    st.warning("База данных пока пуста. Запустите парсер `uv run python main.py --scrape`.")
    st.stop()

# --- Sidebar Filters ---
st.sidebar.header("Фильтры")

platforms = st.sidebar.multiselect("Агрегатор", options=df['platform'].unique(), default=df['platform'].unique())
categories = st.sidebar.multiselect("Категория блюд", options=df['item_category'].unique(), default=df['item_category'].unique())
competitors = st.sidebar.multiselect("Конкуренты", options=df['competitor_name'].unique(), default=list(df['competitor_name'].unique())[:10])

filtered_df = df[
    (df['platform'].isin(platforms)) &
    (df['item_category'].isin(categories)) &
    (df['competitor_name'].isin(competitors))
].copy()

# --- KPIs Calculation ---
if not filtered_df.empty:
    total_items = len(filtered_df)
    promo_items = len(filtered_df[filtered_df['discount_depth'] > 0])
    share_of_promo = (promo_items / total_items) * 100 if total_items > 0 else 0
    
    avg_discount = filtered_df[filtered_df['discount_depth'] > 0]['discount_depth'].mean()
    if pd.isna(avg_discount): avg_discount = 0
    
    # Effective Basket (Burger + Fries + Drink mocked combo price)
    # Simple mock: avg price of 3 random items
    basket_price_ours = filtered_df[filtered_df['is_our_brand']]['base_price'].mean() * 3
    basket_price_competitor = filtered_df[~filtered_df['is_our_brand']]['promo_price'].mean() * 3
    if pd.isna(basket_price_ours): basket_price_ours = 0
    if pd.isna(basket_price_competitor): basket_price_competitor = 0
    
    # Visibility Score: Correlation between discount_depth and (50 - rank)
    correlation = filtered_df['discount_depth'].corr(50 - filtered_df['aggregator_rank'])
    if pd.isna(correlation): correlation = 0
else:
    share_of_promo = avg_discount = basket_price_ours = basket_price_competitor = correlation = 0

# --- Block 1: Executive Summary ---
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f'''
    <div class="glass-card">
        <div class="metric-label">Доля акционных позиций</div>
        <div class="metric-value">{share_of_promo:.1f}%</div>
        <div class="metric-subtext">Рынок залит скидками</div>
    </div>
    ''', unsafe_allow_html=True)
with col2:
    st.markdown(f'''
    <div class="glass-card">
        <div class="metric-label">Средняя глубина скидки</div>
        <div class="metric-value">-{avg_discount:.1f}%</div>
        <div class="metric-subtext">У агрессивных конкурентов</div>
    </div>
    ''', unsafe_allow_html=True)
with col3:
    st.markdown(f'''
    <div class="glass-card">
        <div class="metric-label">Наше комбо vs Конкуренты</div>
        <div class="metric-value">{basket_price_ours:,.0f} ₸ / {basket_price_competitor:,.0f} ₸</div>
        <div class="metric-subtext">Мы дороже на {((basket_price_ours - basket_price_competitor)/max(1, basket_price_competitor)*100):.1f}%</div>
    </div>
    ''', unsafe_allow_html=True)
with col4:
    st.markdown(f'''
    <div class="glass-card">
        <div class="metric-label">Индекс видимости (Корреляция)</div>
        <div class="metric-value">{correlation:.2f}</div>
        <div class="metric-subtext">Как сильно промо влияет на ТОП</div>
    </div>
    ''', unsafe_allow_html=True)

# --- Block 2: Pricing Matrix (Scatterplot) ---
st.markdown("### Матрица ценообразования и выдачи")
if not filtered_df.empty:
    filtered_df['color'] = np.where(
        filtered_df['is_our_brand'], 
        COLOR_OURS, 
        np.where(filtered_df['discount_depth'] > 20, COLOR_COMPETITOR_AGGRESSIVE, COLOR_COMPETITOR)
    )
    
    fig_scatter = px.scatter(
        filtered_df,
        x='base_price',
        y='discount_depth',
        size=(51 - filtered_df['aggregator_rank']), # Larger bubble = better rank (1 is best)
        color='color',
        color_discrete_map="identity",
        hover_name='item_name',
        hover_data={
            'competitor_name': True,
            'base_price': True,
            'promo_price': True,
            'discount_depth': True,
            'aggregator_rank': True,
            'color': False
        },
        labels={
            'base_price': 'Базовая цена (UZS)',
            'discount_depth': 'Глубина скидки (%)'
        },
        title="Позиционирование: Цена vs Скидка (Размер = Позиция в выдаче)"
    )
    fig_scatter.update_layout(
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        font_color='#F8FAFC',
        xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
    )
    st.plotly_chart(fig_scatter, width='stretch')

# --- Block 3: Promo Heatmap & Sales Overlay ---
st.markdown("### Таймлайн агрессивности (Heatmap + Продажи)")

# Generate mock timeseries data for the past 7 days based on hours
dates = pd.date_range(end=datetime.now(), periods=24*7, freq='h')
ts_df = pd.DataFrame({'datetime': dates})
ts_df['hour'] = ts_df['datetime'].dt.hour
ts_df['day'] = ts_df['datetime'].dt.day_name()

# Mock competitor promo intensity (high during lunch and dinner)
ts_df['promo_intensity'] = np.where(
    ts_df['hour'].isin([11, 12, 13, 18, 19, 20]),
    np.random.randint(50, 100, size=len(ts_df)),
    np.random.randint(10, 40, size=len(ts_df))
)

# Mock our sales volume (inversely correlated to competitor promo intensity)
ts_df['our_sales'] = 100 - (ts_df['promo_intensity'] * 0.8) + np.random.randint(-10, 10, size=len(ts_df))

fig_timeline = go.Figure()

# Heatmap for Competitor Promo
# We reshape data for heatmap: x=hours, y=days
heatmap_data = ts_df.pivot_table(index='day', columns='hour', values='promo_intensity')
days_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
heatmap_data = heatmap_data.reindex(days_order)

# Since we want timeline combined, we can use Bar or Heatmap. Let's use a Bar chart overlay for timeline 
# or just plot them on dual axis.
fig_timeline.add_trace(go.Scatter(
    x=ts_df['datetime'],
    y=ts_df['promo_intensity'],
    name="Активность промо конкурентов",
    fill='tozeroy',
    marker_color=COLOR_COMPETITOR_AGGRESSIVE,
    opacity=0.5,
    yaxis='y1'
))

fig_timeline.add_trace(go.Scatter(
    x=ts_df['datetime'],
    y=ts_df['our_sales'],
    name="Наши продажи (Mazzali)",
    mode='lines+markers',
    line=dict(color=COLOR_OURS, width=3),
    yaxis='y2'
))

fig_timeline.update_layout(
    plot_bgcolor='rgba(0,0,0,0)', 
    paper_bgcolor='rgba(0,0,0,0)', 
    font_color='#F8FAFC',
    title="Корреляция: Чужие Акции vs Наши Продажи",
    xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
    yaxis=dict(title='Интенсивность акций', gridcolor='rgba(255,255,255,0.1)'),
    yaxis2=dict(title='Наши продажи', overlaying='y', side='right'),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
)
st.plotly_chart(fig_timeline, width='stretch')

# --- Block 4: Basket Analysis ---
st.markdown("### Анализ Комбо-наборов (Basket Analysis)")

# Group by competitor to find average "Combo" price
# We define a combo as the sum of average price of 3 distinct categories per competitor
if not filtered_df.empty:
    top_competitors = filtered_df.groupby('competitor_name').size().nlargest(10).index
    basket_df = filtered_df[filtered_df['competitor_name'].isin(top_competitors)]
    
    basket_summary = basket_df.groupby(['competitor_name']).agg(
        avg_base=('base_price', 'mean'),
        avg_promo=('promo_price', 'mean')
    ).reset_index()
    
    basket_summary['color'] = np.where(
        basket_summary['competitor_name'].apply(lambda x: any(b.lower() in x.lower() for b in OUR_BRANDS)),
        COLOR_OURS,
        COLOR_COMPETITOR
    )

    fig_basket = go.Figure()
    fig_basket.add_trace(go.Bar(
        x=basket_summary['competitor_name'],
        y=basket_summary['avg_base'],
        name='Базовая стоимость',
        marker_color='rgba(156, 163, 175, 0.3)' # Light grey for base
    ))
    fig_basket.add_trace(go.Bar(
        x=basket_summary['competitor_name'],
        y=basket_summary['avg_promo'],
        name='Стоимость со скидкой',
        marker_color=basket_summary['color']
    ))
    
    fig_basket.update_layout(
        barmode='overlay',
        plot_bgcolor='rgba(0,0,0,0)', 
        paper_bgcolor='rgba(0,0,0,0)', 
        font_color='#F8FAFC',
        title="Сравнение стоимости условной 'Корзины'",
        xaxis=dict(gridcolor='rgba(255,255,255,0.1)'),
        yaxis=dict(gridcolor='rgba(255,255,255,0.1)')
    )
    st.plotly_chart(fig_basket, width='stretch')
