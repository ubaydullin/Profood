import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 1. Настройка страницы
st.set_page_config(page_title="Food Promo Tracker", layout="wide", page_icon="🎯")

def check_password():
    """Returns `True` if the user had the correct login and password."""
    import os
    # Получаем логин и пароль из секретов Streamlit или используем значения по умолчанию
    try:
        correct_login = st.secrets.get("APP_LOGIN", "admin")
        correct_password = st.secrets.get("APP_PASSWORD", "admin123")
    except Exception:
        # Fallback if secrets.toml doesn't exist
        correct_login = os.environ.get("APP_LOGIN", "admin")
        correct_password = os.environ.get("APP_PASSWORD", "admin123")
    
    def password_entered():
        if (
            st.session_state.get("username", "") == correct_login
            and st.session_state.get("password", "") == correct_password
        ):
            st.session_state["password_correct"] = True
            if "password" in st.session_state:
                del st.session_state["password"]
            if "username" in st.session_state:
                del st.session_state["username"]
        else:
            st.session_state["password_correct"] = False

    if st.session_state.get("password_correct", False):
        return True

    # Show inputs
    st.markdown("### 🔐 Вход в систему")
    st.text_input("Логин", key="username")
    st.text_input("Пароль", type="password", key="password")
    st.button("Войти", on_click=password_entered)

    if "password_correct" in st.session_state and not st.session_state["password_correct"]:
        st.error("😕 Неверный логин или пароль")
        
    return False

if not check_password():
    st.stop()

def apply_custom_css():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

    /* Global Typography & Background */
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif !important;
    }
    
    .stApp {
        background-image: 
            radial-gradient(at 0% 0%, rgba(59, 130, 246, 0.15) 0px, transparent 50%),
            radial-gradient(at 100% 100%, rgba(16, 185, 129, 0.1) 0px, transparent 50%);
        background-attachment: fixed;
    }

    /* Sidebar Glassmorphism */
    [data-testid="stSidebar"] {
        background-color: rgba(30, 41, 59, 0.4) !important;
        backdrop-filter: blur(16px) !important;
        -webkit-backdrop-filter: blur(16px) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    /* Metric Cards Glassmorphism */
    [data-testid="stMetric"] {
        background: rgba(30, 41, 59, 0.5);
        backdrop-filter: blur(12px);
        -webkit-backdrop-filter: blur(12px);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 16px;
        padding: 20px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease;
    }
    [data-testid="stMetric"]:hover {
        transform: translateY(-4px);
    }
    
    /* Yandex Design System Cards */
    .yandex-card {
        background-color: #FFFFFF;
        border-radius: 16px;
        padding: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        text-decoration: none;
        color: #000000 !important;
        display: flex;
        flex-direction: column;
        height: 100%;
        margin-bottom: 20px;
    }
    .yandex-card:hover {
        transform: translateY(-5px);
        box-shadow: 0 10px 15px -3px rgba(252, 224, 0, 0.3); /* Yandex Yellow glow */
        text-decoration: none;
    }
    .yandex-card-img {
        width: 100%;
        height: 150px;
        object-fit: cover;
        border-radius: 12px;
        margin-bottom: 12px;
        background-color: #f3f4f6;
    }
    .yandex-badge {
        background-color: #FA4A33; /* Yandex Red */
        color: white;
        padding: 4px 8px;
        border-radius: 8px;
        font-weight: 700;
        font-size: 14px;
        display: inline-block;
        margin-bottom: 8px;
    }
    .yandex-badge-yellow {
        background-color: #FCE000; /* Yandex Yellow */
        color: black;
    }
    .yandex-vendor {
        font-size: 13px;
        color: #6b7280;
        text-transform: uppercase;
        font-weight: 600;
        margin-bottom: 4px;
    }
    .yandex-item {
        font-size: 16px;
        font-weight: 700;
        margin-bottom: auto; /* Push prices to bottom */
        line-height: 1.3;
    }
    .yandex-price-container {
        margin-top: 15px;
        display: flex;
        align-items: baseline;
        gap: 8px;
    }
    .yandex-old-price {
        color: #9ca3af;
        text-decoration: line-through;
        font-size: 14px;
    }
    .yandex-new-price {
        color: #000000;
        font-size: 20px;
        font-weight: 800;
    }
    </style>
    """, unsafe_allow_html=True)

apply_custom_css()


# 2. Загрузка данных (Фокус на скидки)
@st.cache_data(ttl=300)
def load_promo_data():
    try:
        conn = sqlite3.connect("salescrap.db")
        # Забираем только те товары, у которых ЕСТЬ акция (promo_price IS NOT NULL)
        query = """
            SELECT timestamp, aggregator_name, competitor_name, restaurant_url, item_name, item_category,
                   base_price, promo_price, discount_percent, promo_type, promo_condition,
                   free_delivery_threshold, picture_url
            FROM parsed_promos
            WHERE promo_price IS NOT NULL AND discount_percent > 0
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["competitor_name"] = df["competitor_name"].str.strip().str.title()
        
        # Нормализация категорий
        cat_map = {
            "Pizza": "Пицца",
            "Завтрак": "Завтраки",
            "Яндекс комбо": "Комбо",
            "Сеты": "Комбо"
        }
        df["item_category"] = df["item_category"].replace(cat_map)

        # Вытаскиваем Сеты и Комбо из категории Other
        mask_combo = df["item_name"].str.contains(r"комбо|сет|акци", case=False, na=False)
        df.loc[mask_combo & (df["item_category"] == "Other"), "item_category"] = "Комбо"

        # Оставляем только самую СВЕЖУЮ акцию для каждого товара
        df = df.sort_values("timestamp").drop_duplicates(
            subset=["competitor_name", "item_name"], keep="last"
        )
        return df
    except Exception as e:
        st.error(
            f"Ошибка загрузки БД: {e}\n\nБаза данных пуста или не найдена. Запустите парсер (main.py --scrape)."
        )
        return pd.DataFrame()


def get_all_competitors():
    try:
        conn = sqlite3.connect("salescrap.db")
        query = "SELECT DISTINCT competitor_name FROM parsed_promos ORDER BY competitor_name"
        df = pd.read_sql(query, conn)
        conn.close()
        return [name.strip().title() for name in df["competitor_name"] if name]
    except Exception:
        return []

def get_items_for_competitor(competitor_name):
    try:
        conn = sqlite3.connect("salescrap.db")
        # Ищем без учета регистра, так как мы сделали .title()
        query = "SELECT DISTINCT item_name FROM parsed_promos WHERE competitor_name COLLATE NOCASE = ?"
        df = pd.read_sql(query, conn, params=(competitor_name,))
        conn.close()
        return df["item_name"].tolist()
    except Exception:
        return []

def get_item_history(competitor_name, item_name):
    try:
        conn = sqlite3.connect("salescrap.db")
        query = """
            SELECT timestamp, base_price, promo_price
            FROM parsed_promos 
            WHERE competitor_name COLLATE NOCASE = ? AND item_name = ?
            ORDER BY timestamp ASC
        """
        df = pd.read_sql(query, conn, params=(competitor_name, item_name))
        conn.close()
        if not df.empty:
            df["timestamp"] = pd.to_datetime(df["timestamp"])
        return df
    except Exception:
        return pd.DataFrame()


df = load_promo_data()

st.title("🎯 Food Promo Tracker: Радар скидок")

if df.empty:
    st.warning(
        "📭 Нет данных о скидках. Возможно, скрипт парсинга еще работает или конкуренты ничего не предлагают."
    )
    st.stop()

# 3. Сайдбар - Фильтры и TV-режим
st.sidebar.header("Фильтры поиска")
selected_agg = st.sidebar.selectbox(
    "Агрегатор:", ["Все"] + list(df["aggregator_name"].unique())
)
search_query = st.sidebar.text_input(
    "Поиск по заведению или товару:", placeholder="Например: Пицца или Street 77"
)

min_discount = st.sidebar.slider("Минимальная скидка (%)", 0, 100, 15)
only_free_delivery = st.sidebar.toggle("Только бесплатная доставка", False)

st.sidebar.divider()
st.sidebar.subheader("📺 Режим трансляции")
auto_refresh = st.sidebar.toggle("Включить автообновление (каждые 5 мин)", False)
if auto_refresh:
    st_autorefresh(interval=5 * 60 * 1000, key="data_refresh")

filtered_df = df.copy()

if selected_agg != "Все":
    filtered_df = filtered_df[filtered_df["aggregator_name"] == selected_agg]

filtered_df = filtered_df[filtered_df["discount_percent"] >= min_discount]

if only_free_delivery:
    filtered_df = filtered_df[filtered_df["free_delivery_threshold"] == 0]

if search_query:
    query = search_query.lower()
    filtered_df = filtered_df[
        filtered_df["competitor_name"].str.lower().str.contains(query)
        | filtered_df["item_name"].str.lower().str.contains(query)
    ]

# Цвета для наших брендов
color_map = {"Шеф Burger": "#1f77b4", "Mazzali": "#2ca02c"}
for comp in df["competitor_name"].unique():
    if comp not in color_map:
        color_map[comp] = "#7f7f7f"

# --- KPI СВОДКА (TOP LEVEL) ---
market_avg = filtered_df["discount_percent"].mean() if not filtered_df.empty else 0
total_promos = len(filtered_df)

mazzali_avg = filtered_df[filtered_df["competitor_name"] == "Mazzali"][
    "discount_percent"
].mean()
mazzali_avg = mazzali_avg if pd.notna(mazzali_avg) else 0

shef_avg = filtered_df[filtered_df["competitor_name"] == "Шеф Burger"][
    "discount_percent"
].mean()
shef_avg = shef_avg if pd.notna(shef_avg) else 0

maz_delta = mazzali_avg - market_avg
shef_delta = shef_avg - market_avg

max_discount_row = (
    filtered_df.loc[filtered_df["discount_percent"].idxmax()]
    if not filtered_df.empty
    else None
)
max_disc = max_discount_row["discount_percent"] if max_discount_row is not None else 0
max_disc_comp = (
    max_discount_row["competitor_name"]
    if max_discount_row is not None
    else "Нет данных"
)

if not filtered_df.empty:
    top_dumper = filtered_df.groupby("competitor_name").size().idxmax()
    top_dumper_count = filtered_df.groupby("competitor_name").size().max()
else:
    top_dumper = "Нет данных"
    top_dumper_count = 0

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Всего активных акций", f"{total_promos} шт.")
with col2:
    st.metric("Средняя скидка рынка", f"{market_avg:.1f}%")
with col3:
    st.metric("Шеф Burger (Скидка)", f"{shef_avg:.1f}%", f"{shef_delta:.1f}% от рынка")
with col4:
    st.metric("Mazzali (Скидка)", f"{mazzali_avg:.1f}%", f"{maz_delta:.1f}% от рынка")
with col5:
    st.metric(
        f"Главный демпингер: {top_dumper}",
        f"{top_dumper_count} акций",
        f"Макс скидка: {max_disc}%",
    )

st.markdown("---")

# --- ИНСТРУМЕНТЫ ПРОМО-ТРЕКЕРА ---
# 4. Дашборд с вкладками
tab_vitrina, tab1, tab2, tab3, tab4 = st.tabs(
    ["🛒 Витрина скидок", "🚀 Обзор рынка", "🎯 Радар цен", "🍔 Анализ категорий", "📈 История и Экспорт"]
)

with tab_vitrina:
    st.subheader("🔥 Топ-40 лучших скидок")
    top_items = filtered_df.sort_values("discount_percent", ascending=False).head(40)
    
    cols_per_row = 4
    for i in range(0, len(top_items), cols_per_row):
        cols = st.columns(cols_per_row)
        for col, (_, row) in zip(cols, top_items.iloc[i:i+cols_per_row].iterrows()):
            with col:
                pic_url = row['picture_url'] if pd.notna(row['picture_url']) and row['picture_url'] else "https://via.placeholder.com/400x300/202436/FFFFFF?text=No+Image"
                badge_class = "yandex-badge yandex-badge-yellow" if str(row.get('aggregator_name', '')).lower().startswith('yandex') else "yandex-badge"
                
                old_price = int(row['base_price'])
                new_price = int(row['promo_price'])
                disc = int(row['discount_percent'])
                
                html = f"""
                <a href="{row['restaurant_url']}" target="_blank" class="yandex-card">
                    <img src="{pic_url}" class="yandex-card-img" alt="Image">
                    <div>
                        <span class="{badge_class}">-{disc}%</span>
                    </div>
                    <div class="yandex-vendor">{row['competitor_name']}</div>
                    <div class="yandex-item">{row['item_name']}</div>
                    <div class="yandex-price-container">
                        <span class="yandex-new-price">{new_price:,} сум</span>
                        <span class="yandex-old-price">{old_price:,}</span>
                    </div>
                </a>
                """
                st.markdown(html, unsafe_allow_html=True)

with tab1:
    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("Доля агрегаторов")
        agg_share = filtered_df["aggregator_name"].value_counts().reset_index()
        agg_share.columns = ["Агрегатор", "Кол-во акций"]
        fig_pie = px.pie(agg_share, names="Агрегатор", values="Кол-во акций", hole=0.4)
        st.plotly_chart(fig_pie, width="stretch")

    with col_b:
        st.subheader("Топ-10 демпингеров (по количеству акций)")
        top_competitors = (
            filtered_df["competitor_name"].value_counts().head(10).reset_index()
        )
        top_competitors.columns = ["Заведение", "Кол-во акций"]
        fig_bar = px.bar(
            top_competitors,
            x="Заведение",
            y="Кол-во акций",
            color="Заведение",
            text_auto=True,
        )
        fig_bar.update_layout(showlegend=False)
        st.plotly_chart(fig_bar, width="stretch")

with tab2:
    st.subheader("Ценовая политика конкурентов")
    
    # Сортируем для красоты Box-plot
    top_comps_for_box = filtered_df["competitor_name"].value_counts().head(15).index
    box_df = filtered_df[filtered_df["competitor_name"].isin(top_comps_for_box)]
    median_order = box_df.groupby("competitor_name")["discount_percent"].median().sort_values(ascending=False).index

    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Разброс глубины скидок у Топ-15**")
        fig_box = px.box(
            box_df,
            x="competitor_name",
            y="discount_percent",
            color="competitor_name",
            category_orders={"competitor_name": median_order},
            labels={"discount_percent": "Скидка (%)", "competitor_name": "Заведение"},
        )
        fig_box.update_layout(
            showlegend=False, 
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            xaxis_title="",
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig_box, width="stretch")

    with col_b:
        st.markdown("**Матрица цен (Размер и цвет = скидка)**")
        fig_scatter = px.scatter(
            filtered_df,
            x="promo_price",
            y="base_price",
            color="discount_percent",
            color_continuous_scale="Turbo",
            size="discount_percent",
            size_max=15,
            hover_name="item_name",
            hover_data={"competitor_name": True},
            labels={
                "promo_price": "Акционная цена (Сум)",
                "base_price": "Базовая цена (Сум)",
                "discount_percent": "Скидка %"
            },
            opacity=0.7
        )
        max_val = max(filtered_df["base_price"].max(), filtered_df["promo_price"].max()) if not filtered_df.empty else 1000
        fig_scatter.add_shape(
            type="line", x0=0, y0=0, x1=max_val, y1=max_val,
            line=dict(color="rgba(255,255,255,0.5)", dash="dot")
        )
        fig_scatter.update_layout(
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=30, b=0)
        )
        st.plotly_chart(fig_scatter, width="stretch")

with tab3:
    st.subheader("Война категорий: Скидка + Объем")
    st.markdown(
        "Сравнение средней скидки (линия) и количества акционных товаров (столбцы) в разрезе категорий."
    )

    # Считаем среднюю скидку и количество товаров по категориям
    cat_stats = (
        filtered_df.groupby("item_category")
        .agg(
            avg_discount=("discount_percent", "mean"), item_count=("item_name", "count")
        )
        .reset_index()
    )

    # Берем Топ-15 категорий по количеству товаров
    top_cats = cat_stats.sort_values("item_count", ascending=False).head(15)

    # Строим график с двумя осями (Dual-axis)
    fig_dual = go.Figure()
    fig_dual.add_trace(
        go.Bar(
            x=top_cats["item_category"],
            y=top_cats["item_count"],
            name="Кол-во товаров",
            marker_color="royalblue",
            yaxis="y",
        )
    )
    fig_dual.add_trace(
        go.Scatter(
            x=top_cats["item_category"],
            y=top_cats["avg_discount"],
            name="Средняя скидка (%)",
            mode="lines+markers",
            marker=dict(color="firebrick", size=10),
            line=dict(width=3),
            yaxis="y2",
        )
    )

    fig_dual.update_layout(
        title="Анализ топ-категорий",
        xaxis=dict(title="Категория"),
        yaxis=dict(title="Количество товаров (шт)", side="left"),
        yaxis2=dict(
            title="Средняя скидка (%)", side="right", overlaying="y", showgrid=False
        ),
        legend=dict(x=0.01, y=0.99, bgcolor="rgba(255,255,255,0.5)"),
    )
    st.plotly_chart(fig_dual, width="stretch")

with tab4:
    st.subheader("Экспорт и история цен")

    # Выгрузка сырых данных (из отфильтрованного датафрейма)
    st.markdown("### 📋 Выгрузка текущего среза")
    csv = filtered_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="📥 Скачать отфильтрованные данные (CSV)",
        data=csv,
        file_name=f"promo_export_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

    st.markdown("### 📈 Динамика конкретного товара (Вся база)")
    
    col_h1, col_h2 = st.columns(2)
    with col_h1:
        competitors = sorted(list(set(get_all_competitors())))
        if competitors:
            selected_comp = st.selectbox("Выберите заведение для истории", competitors)
        else:
            st.info("Нет данных о заведениях.")
            selected_comp = None

    with col_h2:
        if selected_comp:
            items = sorted(get_items_for_competitor(selected_comp))
            if items:
                selected_item = st.selectbox("Выберите товар", items)
            else:
                st.info("Нет данных о товарах.")
                selected_item = None
        else:
            selected_item = None

    if selected_comp and selected_item:
        item_history = get_item_history(selected_comp, selected_item)

        if not item_history.empty:
            # Заполняем promo_price базовой ценой, если акции не было, чтобы график не обрывался
            item_history["promo_price"] = item_history["promo_price"].fillna(item_history["base_price"])

            fig_hist = go.Figure()
            fig_hist.add_trace(
                go.Scatter(
                    x=item_history["timestamp"],
                    y=item_history["base_price"],
                    mode="lines+markers",
                    name="Старая цена (База)",
                    line=dict(color="gray", dash="dash"),
                )
            )
            fig_hist.add_trace(
                go.Scatter(
                    x=item_history["timestamp"],
                    y=item_history["promo_price"],
                    mode="lines+markers",
                    name="Цена по акции (Фактическая)",
                    line=dict(color="red", width=3),
                )
            )
            fig_hist.update_layout(
                xaxis_title="Время парсинга",
                yaxis_title="Цена (сум)",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
                hovermode="x unified"
            )
            st.plotly_chart(fig_hist, width="stretch")
        else:
            st.info("Нет истории для выбранного товара.")
