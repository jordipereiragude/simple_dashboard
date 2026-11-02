"""Run with: python3 -m streamlit run app.py"""
import html
import math

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
import plotly.io as pio

import charts
from analytics import (ROOT, WORKBOOK, city_totals, filter_orders,
                       load_orders, ranking, summary)

st.set_page_config(page_title="Northwind · Sales overview", page_icon="◼", layout="wide",
                   initial_sidebar_state="expanded")
st.html("<style>" + (ROOT / "assets" / "dashboard.css").read_text() + "</style>")


@st.cache_data(show_spinner=False)
def cached_orders(modified: int) -> pd.DataFrame:
    return load_orders()


@st.cache_data(show_spinner=False)
def cached_coordinates(modified: int) -> pd.DataFrame:
    return pd.read_csv(ROOT / "data" / "city_coordinates.csv")


try:
    orders = cached_orders(WORKBOOK.stat().st_mtime_ns)
    coordinates = cached_coordinates((ROOT / "data" / "city_coordinates.csv").stat().st_mtime_ns)
except (OSError, ValueError) as exc:
    st.error(f"Unable to load dashboard data: {exc}")
    st.stop()

workers = sorted(orders["Worker"].unique().tolist())
countries = sorted(orders["Country"].unique().tolist())
max_sale = float(math.ceil(orders["salesValue"].max() / 500) * 500)

# Initialize and reset through Session State only. Supplying widget defaults as
# well would conflict with the values assigned by the reset callback.
filter_defaults = {
    "workers": workers.copy(),
    "countries": countries.copy(),
    "sales_range": (0.0, max_sale),
}
for key, initial_value in filter_defaults.items():
    if key not in st.session_state:
        st.session_state[key] = initial_value


def reset_filters() -> None:
    st.session_state.update(filter_defaults)


with st.sidebar:
    st.html('<div class="brand"><div class="brand-mark">NW</div><div>'
            '<div class="brand-name">Northwind</div><div class="brand-sub">SALES ANALYTICS</div></div></div>')
    st.html('<div class="eyebrow">A / EXPLORE YOUR DATA</div>'
            '<div class="filter-heading">Filters</div>'
            '<div class="muted">Every view updates as you refine your selection.</div>')
    selected_workers = st.multiselect("Salesperson", workers,
                                      format_func=lambda n: f"Salesperson {n}", key="workers")
    selected_countries = st.multiselect("Country", countries, key="countries")
    value_range = st.slider("Sales value per order ($)", min_value=0.0, max_value=max_sale,
                            step=0.5, format="$%.2f", key="sales_range",
                            help="Inclusive minimum and maximum. Filters individual orders before aggregation.")
    st.caption(f"${value_range[0]:,.2f} — ${value_range[1]:,.2f} · inclusive")
    st.button("Reset filters", on_click=reset_filters, use_container_width=True)
    st.divider()
    st.html('<div class="eyebrow">SOURCE</div><div class="muted">Northwind orders<br>'
            'One row = one delivery order<br>Values shown in $</div>')

filtered = filter_orders(orders, selected_workers, selected_countries, value_range)
stats = summary(filtered)
with st.sidebar:
    st.caption(f"{stats['orders']:,} of {len(orders):,} orders selected")
    st.download_button("Download selected orders", filtered.to_csv(index=False).encode("utf-8"),
                       file_name="northwind_selected_orders.csv", mime="text/csv", use_container_width=True)

st.html(f'<div class="page-heading"><div><div class="eyebrow">NORTHWIND / PERFORMANCE DASHBOARD</div>'
        f'<h1>Sales overview<span style="color:#fe0000">.</span></h1>'
        f'<p>A closer look at your customers, markets and sales team.</p></div>'
        f'<div class="selection-badge"><b>{stats["orders"]:,}</b> / {len(orders):,} orders selected</div></div>')


def kpi(label: str, value: str, note: str, primary: bool = False) -> str:
    return (f'<div class="kpi-card {"primary" if primary else ""}"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>')


def ranking_card(title: str, column: str) -> None:
    rows = ranking(filtered, column, 5)
    body = ""
    for i, row in rows.iterrows():
        body += (f'<div class="ranking-row {"first" if i == 0 else ""}">'
                 f'<span class="ranking-number">{i + 1:02d}</span><span>{html.escape(str(row[column]))}</span>'
                 f'<span class="ranking-value">${row["salesValue"]:,.2f}</span></div>')
    if rows.empty:
        body = '<div class="muted">No matching orders</div>'
    st.html(f'<div class="ranking-card"><div class="card-heading">{title}<span>TOP 5 · SALES</span></div>{body}</div>')


overview = st.columns([1.35, 1, 1], gap="small")
with overview[0]:
    median = "—" if stats["median"] is None else f'${stats["median"]:,.2f}'
    st.html('<div class="kpi-grid">'
            + kpi("Total sales value", f'${stats["sales"]:,.2f}', f'{stats["orders"]:,} delivery orders', True)
            + kpi("Customers", f'{stats["customers"]:,}', "Distinct customer accounts")
            + kpi("Median ticket", median, "Median value per order")
            + kpi("Countries", str(stats["countries"]), "Markets with selected orders") + '</div>')
with overview[1]:
    ranking_card("Top customers", "Client")
with overview[2]:
    ranking_card("Top countries", "Country")

if filtered.empty:
    st.info("No orders match these filters. Select at least one salesperson and country, widen the sales range, or reset filters.")

with st.container(border=True):
    st.html('<div class="panel-heading-row"><div><div class="panel-title"><span class="panel-number">Bx</span>'
            'Sales team at a glance</div><div class="panel-subtitle">Total sales within your selection · all nine salespeople</div></div>'
            '<div class="traffic-legend"><span class="legend-item"><i class="dot" style="background:#fe0000"></i>&lt; $100k</span>'
            '<span class="legend-item"><i class="dot" style="background:#e9b500"></i>$100k–$150k</span>'
            '<span class="legend-item"><i class="dot" style="background:#24935e"></i>&gt; $150k</span>'
            '<span class="legend-item"><i class="dot" style="background:#dedede"></i>No orders</span></div></div>')
    traffic = charts.traffic_lights(filtered, workers, selected_workers)
    # A single Plotly row, with a minimum width and horizontal scroll on small screens.
    # Scatter's marker sizes are measured in pixels, so circles never become ellipses.
    # Streamlit serves custom .js static assets as text/plain + nosniff; embed Plotly
    # in this iframe so the traffic strip also works without a CDN or MIME overrides.
    traffic_html = pio.to_html(traffic, include_plotlyjs=True, full_html=False,
                               config={"displayModeBar": False, "responsive": True}, default_height=220)
    components.html('<style>body{margin:0;background:white;} .strip{min-width:990px;}'
                    'html{scrollbar-width:thin;scrollbar-color:#ccc white;}</style>'
                    '<div role="region" aria-label="Salesperson traffic lights, scroll horizontally on small screens" '
                    'tabindex="0" class="strip">' + traffic_html + '</div>', height=240, scrolling=True)

# Resolve map assets relative to the app document so Cloud's /~/+/ proxy prefix
# (which isn't reflected in server.baseUrlPath) is preserved.
plot_config = {"displaylogo": False, "responsive": True, "scrollZoom": False,
               "topojsonURL": "app/static/", "toImageButtonOptions": {"scale": 2},
               "modeBarButtonsToRemove": ["select2d", "lasso2d"]}


def panel(number: str, title: str, subtitle: str, figure, key: str) -> None:
    with st.container(border=True):
        st.html(f'<div class="panel-title"><span class="panel-number">{number}</span>{title}</div>'
                f'<div class="panel-subtitle">{subtitle}</div>')
        st.plotly_chart(figure, use_container_width=True, theme=None, config=plot_config, key=key)


row_one = st.columns(3, gap="small")
with row_one[0]:
    mean_note = f' · mean ${filtered["salesValue"].mean():,.2f}' if not filtered.empty else ""
    panel("B2", "Order value distribution", "$500 bands · red marks the mean band" + mean_note,
          charts.sales_distribution(filtered), "sales_histogram")
with row_one[1]:
    panel("B3", "Orders per customer", "Customer frequency · red marks the most common order count",
          charts.orders_per_customer(filtered), "customer_histogram")
with row_one[2]:
    panel("B4", "Country concentration", "Sales by country · red is cumulative share · dotted line is 80%",
          charts.country_pareto(filtered), "country_pareto")

row_two = st.columns(3, gap="small")
with row_two[0]:
    panel("B5", "Sales by country", "Total sales · pale blue = no orders in selection",
          charts.country_map(filtered), "country_map")
with row_two[1]:
    cities = city_totals(filtered, coordinates)
    with st.container(border=True):
        st.html('<div class="panel-title"><span class="panel-number">B6</span>Sales by city</div>'
                '<div class="panel-subtitle">Pale blue = map background · dots show sales · scroll to zoom</div>')
        max_marker_size = st.slider("Maximum marker diameter (px)", min_value=3, max_value=18,
                                    value=5, step=1, key="city_size")
        city_figure = charts.city_map(cities, max_marker_size).update_layout(height=225)
        st.plotly_chart(city_figure, use_container_width=True, theme=None,
                        config={**plot_config, "scrollZoom": True}, key="city_map")
        missing = cities["latitude"].isna() | cities["longitude"].isna()
        if missing.any():
            st.warning(f"{int(missing.sum())} cities have no coordinates; their sales remain in all other views.")
with row_two[2]:
    panel("B7", "Ticket spread by salesperson", "Median, quartiles &amp; outliers by salesperson",
          charts.worker_boxplot(filtered, workers), "worker_boxplot")

with st.expander("How to read this dashboard"):
    st.markdown("""
All filters apply together to individual orders before any calculation. One workbook row is one
delivery order; customers are identified by `Client`. Sales and ticket values use `salesValue`.
Clearing a salesperson or country selection gives no results. Reset filters restores all orders.

**Order-value bands** include the lower bound and exclude the upper bound: $0 ≤ value < $500,
$500 ≤ value < $1,000, and so on. The last band includes $5,000 and above, matching the notebook's
calculation. **Orders per customer** groups customers by their order count: a bar at 10 shows how
many customers placed 10 orders. **Pareto** ranks countries by sales and uses a separate percentage
axis for the cumulative line.

**Traffic lights** use the notebook's fixed thresholds: red below $100,000; yellow from $100,000
through $150,000; green above $150,000. All nine employees remain visible; employees without
matching orders have unlit lights. These are absolute totals for the filtered selection.

**Map colors:** pale blue marks countries without orders in the current selection on the country map.
On the city map, pale blue is the land background; the dots carry the sales values.
The gray-to-red scale represents sales in both maps.

**City markers** use log(1 + sales), normalized to the selected maximum diameter (5 pixels by default).
Coordinates are approximate city locations saved locally. **Box plots** use linear quartiles,
whiskers up to 1.5 times the interquartile range, and individual outlier points.
""")
st.html('<div class="footer"><span>NORTHWIND · QUANTITATIVE METHODS FOR DECISION MAKING</span>'
        '<span>Source: northwind-en.xlsx · Interactive Plotly charts</span></div>')
