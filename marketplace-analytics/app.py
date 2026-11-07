from pathlib import Path
import sqlite3
import pandas as pd
import plotly.express as px
import streamlit as st
from marketplace_analytics.analytics import (
    get_orders, filter_orders, kpis, monthly_sales, cohort_retention,
    rfm_segments, delivery_summary,
)
from marketplace_analytics.config import DB
from marketplace_analytics.bootstrap import ensure_demo_database

LABELS = {'order_id': 'ID заказа',
 'customer_unique_id': 'ID покупателя',
 'country': 'Страна',
 'city': 'Город',
 'order_status': 'Статус заказа',
 'order_date': 'Дата заказа',
 'order_month': 'Месяц',
 'delivered_date': 'Дата доставки',
 'estimated_date': 'Ожидаемая дата доставки',
 'gmv': 'GMV (RUB)',
 'freight': 'Стоимость доставки (RUB)',
 'items_count': 'Количество товаров',
 'paid_amount': 'Сумма оплаты (RUB)',
 'review_score': 'Review score',
 'is_late': 'Признак опоздания',
 'delivery_days': 'Delivery days',
 'is_valid': 'Учитывается в метриках',
 'orders': 'Eligible orders',
 'delivery_group': 'Доставка',
 'average_review': 'Average review',
 'low_rating_share': 'Low rating share',
 'segment': 'Сегмент',
 'customers': 'Buyers',
 'total_gmv': 'GMV (RUB)',
 'median_recency': 'Median recency',
 'recency': 'Recency',
 'frequency': 'Frequency',
 'monetary': 'Monetary',
 'rfm_score': 'RFM score'}

st.set_page_config(page_title="Marketplace Analytics", page_icon="📊", layout="wide")
st.title("📊 Marketplace Analytics")
st.caption("Аналитика маркетплейса · Вымышленные демоданные · SQLite + pandas + Streamlit")

@st.cache_data(show_spinner="Загружаем данные...")
def load_data(path: str, modified_at: float) -> pd.DataFrame:
    return get_orders(Path(path))

try:
    with st.spinner("Подготавливаем демоданные и базу SQLite..."):
        ensure_demo_database()
except (OSError, ValueError, sqlite3.Error) as exc:
    st.error(f"Не удалось подготовить демоданные: {exc}")
    st.stop()

all_orders = load_data(str(DB), DB.stat().st_mtime)
if all_orders.empty:
    st.warning("В базе пока нет заказов.")
    st.stop()

with st.sidebar:
    st.header("Фильтры")
    st.caption("Фильтры по дате заказа применяются к вкладкам «Обзор», «Доставка и отзывы» и RFM.")
    first_date = pd.to_datetime(all_orders.order_date.min()).date()
    last_date = pd.to_datetime(all_orders.order_date.max()).date()
    picked = st.date_input("Период покупок", value=(first_date, last_date),
                           min_value=first_date, max_value=last_date)
    countries = sorted(all_orders.country.dropna().unique().tolist())
    selected_countries = st.multiselect("Страна", countries, default=countries)
    cities = sorted(all_orders.loc[all_orders.country.isin(selected_countries), "city"].dropna().unique().tolist())
    selected_cities = st.multiselect("Город", cities, default=cities)
    st.divider()
    st.info("GMV — сумма стоимости товаров без доставки. Отменённые и недоступные заказы исключены. Выручка не равна прибыли.")
    st.caption("Когорты рассчитываются по всей истории покупок. Фильтры по дате, стране и городу на них не влияют.")

if not isinstance(picked, (list, tuple)) or len(picked) != 2:
    st.info("Выберите начало и конец периода.")
    st.stop()
if not selected_countries or not selected_cities:
    st.warning("Выберите хотя бы одну страну и один город.")
    st.stop()
subset = filter_orders(all_orders, picked[0], picked[1], countries=selected_countries, cities=selected_cities)
if subset.empty:
    st.warning("По выбранным фильтрам заказов нет.")
    st.stop()

overview, delivery, cohorts, rfm, data = st.tabs(["Обзор", "Доставка и отзывы", "Когорты", "RFM", "Данные"])
with overview:
    stats = kpis(subset)
    a,b,c,d,e = st.columns(5)
    a.metric("GMV (RUB)", f"₽ {stats['gmv']:,.0f}")
    b.metric("Eligible orders", f"{stats['orders']:,}")
    c.metric("AOV (RUB)", f"₽ {stats['aov']:,.2f}")
    d.metric("Buyers", f"{stats['customers']:,}")
    e.metric("Repeat buyers", f"{stats['repeat_share']:.1%}")
    sales = monthly_sales(subset)
    if not sales.empty:
        st.plotly_chart(px.line(sales, x="order_month", y="gmv", markers=True,
                                title="GMV по месяцам (RUB)", labels={"order_month":"Месяц", "gmv":"GMV, RUB"}),
                        use_container_width=True)
        st.plotly_chart(px.bar(sales, x="order_month", y="orders", title="Eligible orders по месяцам", labels=LABELS),
                        use_container_width=True)
    by_country = subset[subset.is_valid.eq(1)].groupby("country", as_index=False).agg(gmv=("gmv", "sum"))
    st.plotly_chart(px.bar(by_country.sort_values("gmv", ascending=False), x="country", y="gmv",
                           title="GMV по странам покупателей", labels=LABELS), use_container_width=True)

with delivery:
    d = subset[subset.is_late.notna()]
    delayed = d.is_late.mean() if not d.empty else float("nan")
    a,b,c = st.columns(3)
    a.metric("Delivered orders", f"{len(d):,}")
    b.metric("Late delivery share", f"{delayed:.1%}" if pd.notna(delayed) else "N/A")
    c.metric("Avg delivery days", f"{d.delivery_days.mean():.1f}" if not d.empty else "N/A")
    info = delivery_summary(subset)
    if not info.empty:
        info["delivery_group"] = info.delivery_group.replace({"Late": "С опозданием", "On time": "В срок"})
        col1,col2 = st.columns(2)
        with col1:
            st.plotly_chart(px.bar(info, x="delivery_group", y="average_review",
                                   title="Review score в зависимости от доставки", range_y=[0,5],
                                   labels={**LABELS, "average_review":"Average review (1–5)"}), use_container_width=True)
        with col2:
            st.plotly_chart(px.bar(info, x="delivery_group", y="low_rating_share",
                                   title="Low rating share: оценки в 1–2 звезды", labels=LABELS), use_container_width=True)
        st.dataframe(info.rename(columns=LABELS).style.format({"Average review":"{:.2f}","Low rating share":"{:.1%}"}),
                     hide_index=True, use_container_width=True)
    st.caption("Сравнение показывает связь, но не доказывает, что задержки вызывают снижение оценок. Заказы без отзывов исключены.")

with cohorts:
    st.write("Retention показывает возвращаемость покупателей по месяцам на основе учитываемых заказов. В месяц первой покупки (M0) значение равно 100%.")
    co = cohort_retention(all_orders)
    if co.empty:
        st.info("Недостаточно данных для расчёта Retention.")
    else:
        pivot = co[co.period.le(11)].pivot(index="cohort", columns="period", values="retention")
        fig = px.imshow(pivot, text_auto=".0%", aspect="auto", color_continuous_scale="Blues",
                        labels={"x":"Месяцы с первой покупки", "y":"Месяц первой покупки", "color":"Retention"},
                        title="Матрица Когорты")
        st.plotly_chart(fig, use_container_width=True)
        st.caption("У новых когорт меньше месяцев наблюдения. Пустая ячейка означает отсутствие наблюдения, а не нулевой Retention.")

with rfm:
    scores = rfm_segments(subset)
    if scores.empty:
        st.info("В выбранном периоде нет заказов, подходящих для расчёта.")
    else:
        scores["segment"] = scores.segment.replace({
            "Champions": "Лучшие покупатели", "Loyal / potential": "Лояльные / перспективные",
            "Needs attention": "Требуют внимания", "At risk": "Под угрозой ухода",
        })
        groups = scores.groupby("segment", as_index=False).agg(customers=("customer_unique_id","count"),
                          total_gmv=("monetary","sum"), median_recency=("recency","median"))
        a,b = st.columns(2)
        with a:
            st.plotly_chart(px.pie(groups, names="segment", values="customers",
                                   title="Сегменты покупателей по RFM score", labels=LABELS), use_container_width=True)
        with b:
            st.plotly_chart(px.bar(groups, x="segment", y="total_gmv", title="GMV по сегментам RFM", labels=LABELS),
                            use_container_width=True)
        st.dataframe(groups.rename(columns=LABELS), hide_index=True, use_container_width=True)
        st.download_button("Скачать RFM в CSV", scores.to_csv(index=False).encode("utf-8"),
                           "rfm_segments.csv", mime="text/csv")
        st.caption("RFM пересчитывается для выбранного периода, стран и городов. Для сегментации по всей истории выберите весь период. Сегменты определяются эвристическими правилами.")

with data:
    st.subheader("Данные на уровне заказов")
    st.write(f"{len(subset):,} строк после фильтрации (включая заказы, исключённые из расчёта GMV, для анализа доставки).")
    st.dataframe(subset.head(2000).assign(order_status=lambda df: df.order_status.replace({"delivered":"Доставлен", "shipped":"В пути", "canceled":"Отменён", "unavailable":"Недоступен"})).rename(columns=LABELS), use_container_width=True, hide_index=True)
    st.download_button("Скачать выбранные заказы в CSV", subset.to_csv(index=False).encode("utf-8"),
                       "marketplace_orders.csv", mime="text/csv")

st.divider()
st.caption("Все данные вымышлены и сгенерированы для проекта. Метрики показывают работу методов анализа, а не результаты реального маркетплейса.")
