import streamlit as st
import pandas as pd
import plotly.express as px
import sqlite3
from analytics.anomaly import AnomalyDetector

st.set_page_config(
    page_title="Promotion Intelligence",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# --- Dark Glassmorphism SaaS CSS ---
st.markdown(
    """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Satoshi:wght@300;400;500;700&display=swap');
    
    .stApp {
        background-color: #0B0E14;
        background-image: 
            radial-gradient(circle at 15% 50%, rgba(0, 240, 255, 0.05), transparent 25%),
            radial-gradient(circle at 85% 30%, rgba(255, 0, 102, 0.05), transparent 25%);
        color: #E2E8F0;
        font-family: 'Satoshi', sans-serif;
    }
    
    .glass-card {
        background: rgba(20, 25, 35, 0.6);
        backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 24px;
        box-shadow: 0 8px 32px 0 rgba(0, 0, 0, 0.3);
        margin-bottom: 24px;
    }
    
    .metric-value {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, #00F0FF, #3B82F6);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 8px;
    }
    
    .metric-label {
        font-size: 0.9rem;
        color: #94A3B8;
        text-transform: uppercase;
        letter-spacing: 1px;
        font-weight: 500;
    }
</style>
""",
    unsafe_allow_html=True,
)

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect('salescrap.db')
    query = "SELECT * FROM parsed_promos"
    df = pd.read_sql(query, conn)
    conn.close()
    
    if df.empty:
        return df
        
    # Sort by timestamp to ensure we keep the latest
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df = df.sort_values('timestamp')
    
    # Drop duplicates keeping the latest scrape
    df = df.drop_duplicates(subset=['competitor_name', 'item_name'], keep='last')
    
    # Create final_price for analytics
    df['final_price'] = df['promo_price'].fillna(df['base_price'])
    
    # Fill rating NaN with average
    df['rating_score'] = df['rating_score'].fillna(4.5)
    df['reviews_count'] = df['reviews_count'].fillna(0)
    
    return df

st.markdown(
    "<h1>Promotion Intelligence <span style='color: #00F0FF'>Platform</span></h1>",
    unsafe_allow_html=True,
)

df = load_data()

if df.empty:
    st.warning("База данных пуста. Пожалуйста, запустите скрапер (main.py --scrape).")
    st.stop()

# KPIs
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f'<div class="glass-card"><div class="metric-label">Active Items</div><div class="metric-value">{len(df)}</div></div>',
        unsafe_allow_html=True,
    )
with col2:
    avg_discount = df['discount_percent'].dropna().mean()
    if pd.isna(avg_discount):
        avg_discount = 0.0
    st.markdown(
        f'<div class="glass-card"><div class="metric-label">Avg Discount</div><div class="metric-value" style="background: linear-gradient(90deg, #F43F5E, #EC4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">{avg_discount:.1f}%</div></div>',
        unsafe_allow_html=True,
    )
with col3:
    promos_count = len(df[df['discount_percent'] > 0])
    st.markdown(
        f'<div class="glass-card"><div class="metric-label">Promotions</div><div class="metric-value">{promos_count}</div></div>',
        unsafe_allow_html=True,
    )

tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["BizDev Insights", "Top Discounts", "Product Search", "Market Overview", "Price Anomalies"]
)

with tab1:
    st.markdown("<h2>📊 BizDev Анализ: Конкурентная Разведка</h2>", unsafe_allow_html=True)
    st.markdown("Сравните ваши бренды (Mazzali, Шеф Burger) с рынком по конкретному продукту.")
    
    search_term = st.text_input("Введите название товара для анализа (например: 'Бургер', 'Лаваш', 'Пицца'):", value="Бургер")
    
    if search_term:
        # Filter by item name (case insensitive)
        biz_df = df[df['item_name'].str.contains(search_term, case=False, na=False)].copy()
        
        if biz_df.empty:
            st.warning(f"Не найдено товаров по запросу '{search_term}'")
        else:
            # Color map for our brands
            def get_color(brand_name):
                name = str(brand_name).lower()
                if 'mazzali' in name:
                    return 'Mazzali'
                elif 'шеф burger' in name or 'shef burger' in name:
                    return 'Шеф Burger'
                return 'Конкурент'
                
            biz_df['Brand_Type'] = biz_df['competitor_name'].apply(get_color)
            color_discrete_map = {
                'Mazzali': '#2ca02c',       # Green
                'Шеф Burger': '#1f77b4',     # Blue
                'Конкурент': '#94A3B8'       # Gray
            }
            
            st.markdown("### 1. Матрица Цена-Качество (Price vs. Trust)")
            
            fig1 = px.scatter(
                biz_df,
                x='final_price',
                y='rating_score',
                size='reviews_count',
                color='Brand_Type',
                color_discrete_map=color_discrete_map,
                hover_name='competitor_name',
                hover_data=['item_name'],
                title=f'Расстановка сил на рынке: {search_term}',
                labels={
                    'final_price': 'Итоговая цена (Сум)',
                    'rating_score': 'Рейтинг',
                    'reviews_count': 'Кол-во отзывов'
                }
            )
            
            # Add average lines
            market_avg_price = biz_df['final_price'].mean()
            market_avg_rating = biz_df['rating_score'].mean()
            fig1.add_vline(x=market_avg_price, line_dash="dash", line_color="red", annotation_text="Средняя цена")
            fig1.add_hline(y=market_avg_rating, line_dash="dash", line_color="red", annotation_text="Средний рейтинг")
            
            fig1.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0")
            fig1.update_xaxes(range=[0, 100000]) # Ограничиваем просмотр до 100к сум
            fig1.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
            st.plotly_chart(fig1, use_container_width=True)
            
            st.markdown("### 2. Калькулятор Истинной Стоимости (True Cost)")
            st.markdown("Сравнение стоимости товара с учетом скрытых платежей (Доставка + Сервис).")
            
            # Stacked bar
            true_cost_df = biz_df.copy()
            # We want to show top 20 or so if there are too many
            true_cost_df['Total_Cost'] = true_cost_df['final_price'] + true_cost_df['delivery_fee'].fillna(0) + true_cost_df['service_fee'].fillna(0)
            true_cost_df = true_cost_df.sort_values('Total_Cost').head(30) # top 30 cheapest
            
            melted_cost = pd.melt(
                true_cost_df, 
                id_vars=['competitor_name', 'Brand_Type', 'item_name'], 
                value_vars=['final_price', 'delivery_fee', 'service_fee'],
                var_name='Component', 
                value_name='Cost'
            )
            melted_cost['Component'] = melted_cost['Component'].map({
                'final_price': 'Цена Товара',
                'delivery_fee': 'Доставка',
                'service_fee': 'Сервисный сбор'
            })
            
            fig2 = px.bar(
                melted_cost,
                x='competitor_name',
                y='Cost',
                color='Component',
                title=f'Истинная стоимость чека (Товар + Доставка): {search_term}',
                hover_data=['item_name', 'Brand_Type']
            )
            fig2.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0", xaxis_title="Заведение", yaxis_title="Сумма (Сум)", barmode='stack')
            st.plotly_chart(fig2, use_container_width=True)
            
            st.markdown("### 3. Воронка Видимости (Visibility Gap)")
            st.markdown("На каком месте в ленте агрегатора находится заведение?")
            
            # 1. Приводим названия к одному регистру
            biz_df['competitor_name'] = biz_df['competitor_name'].str.strip().str.title()
            
            # 2. Убираем ритейл (хардкод-фильтр для чистоты)
            retail_trash = ['Makro', 'Zoo Planeta', 'Korzinka Go', 'The Loaf'] 
            biz_df = biz_df[~biz_df['competitor_name'].isin(retail_trash)]
            
            # 3. Берем минимальную позицию (убираем дубли в рамках одного бренда)
            vis_df = biz_df.groupby(['aggregator_name', 'competitor_name', 'is_in_carousel', 'Brand_Type'])['position_in_list'].min().reset_index()
            vis_df = vis_df.sort_values('position_in_list')
            
            fig3 = px.bar(
                vis_df.head(40),
                x='competitor_name',
                y='position_in_list',
                color='Brand_Type',
                color_discrete_map=color_discrete_map,
                pattern_shape='is_in_carousel',
                title='Место в выдаче (Меньше = Выше)',
                facet_col='aggregator_name'
            )
            fig3.update_layout(plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", font_color="#E2E8F0", yaxis_autorange="reversed")
            st.plotly_chart(fig3, use_container_width=True)


with tab2:
    st.markdown("<h3>Top Active Discounts</h3>", unsafe_allow_html=True)
    top_discounts = df[df["discount_percent"] > 0].sort_values(by="discount_percent", ascending=False).head(50)
    st.dataframe(
        top_discounts[
            [
                "timestamp",
                "aggregator_name",
                "competitor_name",
                "item_name",
                "discount_percent",
                "final_price",
                "base_price"
            ]
        ],
        use_container_width=True,
        hide_index=True,
    )

with tab3:
    st.markdown("<h3>Search All Products</h3>", unsafe_allow_html=True)
    search_query = st.text_input("Enter product name (e.g., 'Lavash')", key="search_all")
    if search_query:
        results = df[df["item_name"].str.contains(search_query, case=False, na=False)]
        if not results.empty:
            results = results.sort_values(by="final_price", ascending=True)
            st.dataframe(
                results[
                    [
                        "aggregator_name",
                        "competitor_name",
                        "item_category",
                        "item_name",
                        "final_price",
                        "base_price",
                    ]
                ],
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.warning("No products found matching your search.")

with tab4:
    st.markdown("<h3>Market by Category</h3>", unsafe_allow_html=True)
    category_counts = (
        df.groupby(["item_category", "aggregator_name"]).size().reset_index(name="count")
    )
    # Filter top 20 categories for visualization
    top_categories = category_counts.groupby('item_category')['count'].sum().nlargest(20).index
    category_counts = category_counts[category_counts['item_category'].isin(top_categories)]
    
    fig = px.bar(
        category_counts, x="item_category", y="count", color="aggregator_name", barmode="group"
    )
    fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#E2E8F0",
    )
    st.plotly_chart(fig, use_container_width=True)

    st.markdown("<h3>Platform Dominance by Total Items</h3>", unsafe_allow_html=True)
    pie_fig = px.pie(df, names="aggregator_name", title="Platform Dominance")
    pie_fig.update_layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font_color="#E2E8F0",
    )
    st.plotly_chart(pie_fig, use_container_width=True)

with tab5:
    st.markdown("<h3>Brand Loyalty Anomalies</h3>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color:#94A3B8;'>Dishes that are more expensive but get bought more frequently due to brand trust (measured by review counts).</p>",
        unsafe_allow_html=True,
    )

    detector = AnomalyDetector(df.to_dict('records'))
    anomalies = detector.detect_premium_brand_anomalies()

    if not anomalies.empty:
        st.dataframe(anomalies, use_container_width=True, hide_index=True)
    else:
        st.info("No anomalies detected currently.")
