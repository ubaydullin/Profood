import streamlit as st
import pandas as pd
import sqlite3
import plotly.express as px

# 1. Настройка страницы
st.set_page_config(page_title="BizDev Promo Tracker", layout="wide", initial_sidebar_state="expanded")

# 2. Загрузка данных из SQLite
@st.cache_data(ttl=300) # Обновление каждые 5 минут
def load_data():
    try:
        conn = sqlite3.connect('salescrap.db')
        query = """
            SELECT timestamp, aggregator_name, competitor_name, item_name, item_category,
                   base_price, promo_price, promo_type, is_in_carousel, position_in_list,
                   delivery_fee, service_fee, free_delivery_threshold, 
                   rating_score, reviews_count
            FROM parsed_promo
        """
        df = pd.read_sql(query, conn)
        conn.close()
        
        if df.empty:
            return df
            
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Очистка названий брендов от проблем с регистром и пробелами
        df['competitor_name'] = df['competitor_name'].str.strip().str.title()
        
        # Расчет итоговой цены товара (Если есть скидка - берем ее, иначе базу)
        df['final_price'] = df['promo_price'].fillna(df['base_price'])
        
        # Обработка пустых рейтингов (чтобы график не падал)
        df['rating_score'] = df['rating_score'].fillna(0)
        df['reviews_count'] = df['reviews_count'].fillna(10) # Заглушка для невидимых пузырьков
        
        # Дедупликация: Оставляем только самую СВЕЖУЮ цену для каждого товара в каждом заведении
        df = df.sort_values('timestamp').drop_duplicates(
            subset=['aggregator_name', 'competitor_name', 'item_name'], 
            keep='last'
        )
        return df
    except Exception as e:
        st.error(f"Ошибка загрузки БД: {e}")
        return pd.DataFrame()

# 3. Интерфейс и Фильтры
st.title("🍔 BizDev Insights: Конкурентный анализ")

df = load_data()

if df.empty:
    st.warning("База данных пуста или не найдена. Запустите парсер (main.py --scrape).")
    st.stop()

# Боковая панель
st.sidebar.header("Параметры анализа")
selected_aggregator = st.sidebar.selectbox("Агрегатор:", ["Все"] + list(df['aggregator_name'].unique()))

if selected_aggregator != "Все":
    df = df[df['aggregator_name'] == selected_aggregator]

# Гибкий текстовый поиск товара (Главное оружие BizDev)
st.sidebar.markdown("---")
st.sidebar.subheader("Поиск по меню")
search_query = st.sidebar.text_input("Введите название (например, Бургер, Лаваш):", value="Бургер")

# Фильтрация по поиску
filtered_df = df[df['item_name'].str.contains(search_query, case=False, na=False)]

if filtered_df.empty:
    st.info(f"По запросу '{search_query}' ничего не найдено.")
    st.stop()

# Цветовая схема для выделения наших брендов
color_map = {
    'Шеф Burger': '#1f77b4',  # Синий
    'Mazzali': '#2ca02c',     # Зеленый
}
# Назначаем серый цвет остальным конкурентам
for comp in filtered_df['competitor_name'].unique():
    if comp not in color_map:
        color_map[comp] = '#7f7f7f' # Серый

# 4. Вкладки (Инструменты BizDev)
tab1, tab2, tab3 = st.tabs(["Матрица Цена-Качество", "Истинная стоимость чека", "Воронка видимости"])

with tab1:
    st.subheader(f"Расстановка сил на рынке: {search_query}")
    st.markdown("Кто забирает трафик за счет лучшего баланса рейтинга и цены?")
    
    # Фильтруем заведения с нулевым рейтингом, чтобы не портить масштаб
    matrix_df = filtered_df[filtered_df['rating_score'] > 3.0]
    
    if not matrix_df.empty:
        fig1 = px.scatter(
            matrix_df,
            x='final_price', y='rating_score', size='reviews_count',
            color='competitor_name', color_discrete_map=color_map,
            hover_name='item_name',
            labels={'final_price': 'Цена (Сум)', 'rating_score': 'Рейтинг', 'competitor_name': 'Бренд'}
        )
        
        # Линии средних значений
        avg_price = matrix_df['final_price'].mean()
        avg_rating = matrix_df['rating_score'].mean()
        fig1.add_vline(x=avg_price, line_dash="dash", line_color="red", annotation_text="Средняя цена")
        fig1.add_hline(y=avg_rating, line_dash="dash", line_color="red", annotation_text="Средний рейтинг")
        
        # Защита от выбросов (например, комбо за 300к)
        q3 = matrix_df['final_price'].quantile(0.95)
        fig1.update_xaxes(range=[0, q3 * 1.2]) # Отрезаем топ 5% самых дорогих товаров
        
        fig1.update_traces(marker=dict(line=dict(width=1, color='DarkSlateGrey')))
        st.plotly_chart(fig1, width="stretch")
    else:
        st.write("Недостаточно данных о рейтингах для построения матрицы.")

with tab2:
    st.subheader("Что реально платит клиент (Скрытые переплаты)")
    st.markdown("Сравнение стоимости товара и наценок за доставку/сервис.")
    
    # Для этого графика берем среднюю цену товара по каждому бренду
    cost_df = filtered_df.groupby(['competitor_name', 'aggregator_name']).agg({
        'final_price': 'mean',
        'delivery_fee': 'first', # Доставка обычно одинаковая для всего ресторана
        'service_fee': 'first'
    }).reset_index()
    
    # Преобразуем для Stacked Bar
    cost_melt = cost_df.melt(
        id_vars=['competitor_name', 'aggregator_name'],
        value_vars=['final_price', 'delivery_fee', 'service_fee'],
        var_name='Тип расхода', value_name='Сумма'
    )
    # Красивые названия
    cost_melt['Тип расхода'] = cost_melt['Тип расхода'].replace({
        'final_price': 'Цена товара', 'delivery_fee': 'Доставка', 'service_fee': 'Сервисный сбор'
    })
    
    fig2 = px.bar(
        cost_melt,
        x='competitor_name', y='Сумма', color='Тип расхода',
        facet_col='aggregator_name',
        title="Структура чека (Товар + Доставка)",
        labels={'competitor_name': 'Заведение'}
    )
    st.plotly_chart(fig2, width="stretch")

with tab3:
    st.subheader("Позиции в выдаче агрегатора")
    st.markdown("Чем ниже столбец, тем лучше. Кто покупает места в карусели?")
    
    # Берем минимальную (лучшую) позицию ресторана за день
    vis_df = df.groupby(['aggregator_name', 'competitor_name', 'is_in_carousel'])['position_in_list'].min().reset_index()
    
    # Ограничиваем список топ-30, чтобы график читался
    vis_df = vis_df[vis_df['position_in_list'] <= 30].sort_values('position_in_list')
    
    fig3 = px.bar(
        vis_df,
        x='competitor_name', y='position_in_list',
        color='competitor_name', color_discrete_map=color_map,
        facet_col='aggregator_name',
        pattern_shape='is_in_carousel', # Штриховка, если место куплено
        labels={'position_in_list': 'Позиция (Меньше = Выше)'}
    )
    # Инвертируем ось Y, чтобы 1-е место было сверху
    fig3.update_yaxes(autorange="reversed")
    st.plotly_chart(fig3, width="stretch")
