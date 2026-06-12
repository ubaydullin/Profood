import streamlit as st
import pandas as pd
import plotly.express as px
from analytics.category_mapper import map_restaurant_category
from analytics.anomaly import AnomalyDetector

st.set_page_config(page_title="Promotion Intelligence", layout="wide", initial_sidebar_state="collapsed")

# --- Dark Glassmorphism SaaS CSS ---
st.markdown("""
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
""", unsafe_allow_html=True)

# Mock Data Generation
def get_mock_data():
    data = [
        {'platform': 'Uzum Tezkor', 'restaurant_name': 'Evos', 'promo_title': 'Lavash Meat', 'current_price': 30000, 'restaurant_reviews': 5000, 'discount_percent': 10},
        {'platform': 'Yandex Eda', 'restaurant_name': 'Oqtepa Lavash', 'promo_title': 'Lavash Meat', 'current_price': 25000, 'restaurant_reviews': 3000, 'discount_percent': 15},
        {'platform': 'Uzum Tezkor', 'restaurant_name': 'MaxWay', 'promo_title': 'Cheese Burger', 'current_price': 35000, 'restaurant_reviews': 8000, 'discount_percent': 5},
        {'platform': 'Yandex Eda', 'restaurant_name': 'FeedUp', 'promo_title': 'Cheese Burger', 'current_price': 28000, 'restaurant_reviews': 1200, 'discount_percent': 20},
        {'platform': 'Uzum Tezkor', 'restaurant_name': 'Safia', 'promo_title': 'Honey Cake', 'current_price': 40000, 'restaurant_reviews': 10000, 'discount_percent': 0},
    ]
    df = pd.DataFrame(data)
    df['category'] = df['restaurant_name'].apply(map_restaurant_category)
    return data, df

st.markdown("<h1>Promotion Intelligence <span style='color: #00F0FF'>Platform</span></h1>", unsafe_allow_html=True)

raw_data, df = get_mock_data()

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown('<div class="glass-card"><div class="metric-label">Active Promos</div><div class="metric-value">1,248</div></div>', unsafe_allow_html=True)
with col2:
    st.markdown('<div class="glass-card"><div class="metric-label">Avg Discount</div><div class="metric-value" style="background: linear-gradient(90deg, #F43F5E, #EC4899); -webkit-background-clip: text; -webkit-text-fill-color: transparent;">18.5%</div></div>', unsafe_allow_html=True)

tab1, tab2 = st.tabs(["Market Activity", "Price Anomalies (Premium Brand)"])

with tab1:
    st.markdown("<h3>Market by Category</h3>", unsafe_allow_html=True)
    category_counts = df.groupby(['category', 'platform']).size().reset_index(name='count')
    fig = px.bar(category_counts, x='category', y='count', color='platform', barmode='group')
    fig.update_layout(plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font_color='#E2E8F0')
    st.plotly_chart(fig, use_container_width=True)

with tab2:
    st.markdown("<h3>Brand Loyalty Anomalies</h3>", unsafe_allow_html=True)
    st.markdown("<p style='color:#94A3B8;'>Dishes that are more expensive but get bought more frequently due to brand trust.</p>", unsafe_allow_html=True)
    
    detector = AnomalyDetector(raw_data)
    anomalies = detector.detect_premium_brand_anomalies()
    
    if not anomalies.empty:
        st.dataframe(anomalies, use_container_width=True, hide_index=True)
    else:
        st.info("No anomalies detected currently.")
