import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
from streamlit_autorefresh import st_autorefresh

# 1. Настройка страницы
st.set_page_config(page_title="Food Promo Tracker", layout="wide", page_icon="🎯")


# 2. Загрузка данных (Фокус на скидки)
@st.cache_data(ttl=300)
def load_promo_data():
    try:
        conn = sqlite3.connect("salescrap.db")
        # Забираем только те товары, у которых ЕСТЬ акция (promo_price IS NOT NULL)
        query = """
            SELECT timestamp, aggregator_name, competitor_name, restaurant_url, item_name, item_category,
                   base_price, promo_price, discount_percent, promo_type, promo_condition,
                   free_delivery_threshold
            FROM parsed_promos
            WHERE promo_price IS NOT NULL AND discount_percent > 0
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["competitor_name"] = df["competitor_name"].str.strip().str.title()

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


@st.cache_data(ttl=300)
def load_history_data():
    try:
        conn = sqlite3.connect("salescrap.db")
        query = """
            SELECT timestamp, aggregator_name, competitor_name, restaurant_url, item_name, item_category,
                   base_price, promo_price, discount_percent, promo_type, promo_condition,
                   free_delivery_threshold
            FROM parsed_promos
            WHERE promo_price IS NOT NULL AND discount_percent > 0
        """
        df = pd.read_sql(query, conn)
        conn.close()

        if df.empty:
            return df

        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["competitor_name"] = df["competitor_name"].str.strip().str.title()

        df = df.sort_values("timestamp")
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
tab1, tab2, tab3, tab4 = st.tabs(
    ["🚀 Обзор рынка", "🎯 Радар цен", "🍔 Анализ категорий", "📈 История и Экспорт"]
)

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
            color_discrete_map=color_map,
            text_auto=True,
        )
        st.plotly_chart(fig_bar, width="stretch")

with tab2:
    st.subheader("Ценовая политика конкурентов")
    col_a, col_b = st.columns(2)

    with col_a:
        st.markdown("**Разброс глубины скидок (Box-plot)**")
        # Берем топ-15 заведений по количеству акций, чтобы график не был слишком длинным
        top_comps_for_box = filtered_df["competitor_name"].value_counts().head(15).index
        box_df = filtered_df[filtered_df["competitor_name"].isin(top_comps_for_box)]
        fig_box = px.box(
            box_df,
            x="competitor_name",
            y="discount_percent",
            color="competitor_name",
            color_discrete_map=color_map,
            labels={"discount_percent": "Скидка (%)", "competitor_name": "Заведение"},
        )
        st.plotly_chart(fig_box, width="stretch")

    with col_b:
        st.markdown("**Матрица цен: База vs Акция (Scatter-plot)**")
        fig_scatter = px.scatter(
            filtered_df,
            x="promo_price",
            y="base_price",
            size="discount_percent",
            color="competitor_name",
            color_discrete_map=color_map,
            hover_name="item_name",
            labels={
                "promo_price": "Акционная цена (Сум)",
                "base_price": "Базовая цена (Сум)",
            },
        )
        max_val = max(filtered_df["base_price"].max(), filtered_df["promo_price"].max())
        fig_scatter.add_shape(
            type="line",
            x0=0,
            y0=0,
            x1=max_val,
            y1=max_val,
            line=dict(color="red", dash="dash"),
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

    st.dataframe(
        filtered_df[
            [
                "aggregator_name",
                "competitor_name",
                "restaurant_url",
                "item_name",
                "discount_percent",
                "promo_price",
                "base_price",
                "promo_type",
            ]
        ],
        column_config={
            "aggregator_name": "Агрегатор",
            "competitor_name": "Заведение",
            "restaurant_url": st.column_config.LinkColumn(
                "Ссылка", display_text="Открыть 🛒"
            ),
            "item_name": "Товар",
            "discount_percent": st.column_config.ProgressColumn(
                "Скидка %", format="%f%%", min_value=0, max_value=100
            ),
            "promo_price": "Цена по акции",
            "base_price": "Старая цена",
            "promo_type": "Тип",
        },
        width="stretch",
        hide_index=True,
        height=300,
    )

    st.markdown("### 📈 Динамика конкретного товара")
    history_df = load_history_data()
    if not history_df.empty:
        col_h1, col_h2 = st.columns(2)
        with col_h1:
            competitors = sorted(history_df["competitor_name"].unique())
            selected_comp = st.selectbox("Выберите заведение для истории", competitors)

        with col_h2:
            items = sorted(
                history_df[history_df["competitor_name"] == selected_comp][
                    "item_name"
                ].unique()
            )
            selected_item = st.selectbox("Выберите товар", items)

        item_history = history_df[
            (history_df["competitor_name"] == selected_comp)
            & (history_df["item_name"] == selected_item)
        ]

        if not item_history.empty:
            fig_hist = go.Figure()
            fig_hist.add_trace(
                go.Scatter(
                    x=item_history["timestamp"],
                    y=item_history["base_price"],
                    mode="lines+markers",
                    name="Старая цена",
                    line=dict(color="gray", dash="dash"),
                )
            )
            fig_hist.add_trace(
                go.Scatter(
                    x=item_history["timestamp"],
                    y=item_history["promo_price"],
                    mode="lines+markers",
                    name="Цена по акции",
                    line=dict(color="red", width=3),
                )
            )
            fig_hist.update_layout(
                xaxis_title="Время",
                yaxis_title="Цена (сум)",
                legend=dict(
                    orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1
                ),
            )
            st.plotly_chart(fig_hist, width="stretch")
        else:
            st.info("Нет истории для выбранного товара.")
