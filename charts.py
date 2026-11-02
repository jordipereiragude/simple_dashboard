"""Plotly charts for every panel of the Northwind dashboard."""
import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from analytics import (country_totals, customer_frequency, employee_status,
                       employee_totals, sales_histogram)

RED = "#fe0000"
GRAY = "#878787"
INK = "#252525"
GRID = "#eeeeee"
MAP_LAND = "#dcebf7"
SCALE = [[0, "#ededed"], [0.45, "#b5b5b5"], [0.8, "#646464"], [1, RED]]


def base(fig: go.Figure, height: int = 300) -> go.Figure:
    fig.update_layout(
        template="plotly_white", height=height,
        font=dict(family="Arial, sans-serif", size=12, color="#686868"),
        paper_bgcolor="white", plot_bgcolor="white",
        margin=dict(l=12, r=12, t=16, b=12),
        hoverlabel=dict(bgcolor=INK, font_color="white", font_size=13),
        showlegend=False, dragmode=False,
    )
    fig.update_xaxes(showgrid=False, zeroline=False, automargin=True, title_font_size=12)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, automargin=True, title_font_size=12)
    return fig


def empty(message: str = "No orders match these filters.", height: int = 300) -> go.Figure:
    fig = base(go.Figure(), height)
    fig.add_annotation(text=message, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    return fig


def sales_distribution(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty()
    counts, mean_bin = sales_histogram(df)
    fig = base(go.Figure(go.Bar(
        x=counts.index.tolist(), y=counts.tolist(),
        marker_color=[RED if label == mean_bin else GRAY for label in counts.index],
        hovertemplate="Order value: %{x}<br>%{y:,} orders<extra></extra>",
    )))
    fig.update_layout(bargap=0.22)
    fig.update_xaxes(title="Order value ($)", tickangle=-55, tickfont_size=10)
    fig.update_yaxes(title="Orders", rangemode="tozero", dtick=None)
    return fig


def orders_per_customer(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty()
    counts = customer_frequency(df)
    mode = counts.idxmax()
    fig = base(go.Figure(go.Bar(
        x=counts.index.tolist(), y=counts.tolist(),
        marker_color=[RED if n == mode else GRAY for n in counts.index],
        hovertemplate="%{x} orders per customer<br>%{y} customers<extra></extra>",
    )))
    fig.update_xaxes(title="Orders per customer", dtick=max(1, int(np.ceil(len(counts) / 10))))
    fig.update_yaxes(title="Customers", rangemode="tozero", dtick=1 if counts.max() < 10 else None)
    return fig


def country_pareto(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty()
    countries = country_totals(df)
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(go.Bar(
        x=countries["Country"].tolist(), y=countries["salesValue"].tolist(),
        marker_color=GRAY, name="Sales", customdata=countries[["share"]].values.tolist(),
        hovertemplate="%{x}<br>$%{y:,.2f}<br>%{customdata[0]:.1f}% of sales<extra></extra>",
    ), secondary_y=False)
    fig.add_trace(go.Scatter(
        x=countries["Country"].tolist(), y=countries["cumulative"].tolist(),
        mode="lines+markers", line=dict(color=RED, width=2), marker=dict(size=4), name="Cumulative %",
        hovertemplate="Through %{x}<br>%{y:.1f}% cumulative sales<extra></extra>",
    ), secondary_y=True)
    base(fig)
    fig.add_hline(y=80, line_dash="dot", line_color="#b0b0b0", secondary_y=True)
    fig.update_xaxes(tickangle=-65, tickfont_size=10)
    fig.update_yaxes(title="Sales ($)", tickformat="~s", secondary_y=False, rangemode="tozero")
    fig.update_yaxes(title=None, ticksuffix="%", range=[0, 105], dtick=20, showgrid=False, secondary_y=True)
    return fig


def map_base(fig: go.Figure) -> go.Figure:
    base(fig)
    fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), dragmode="pan")
    fig.update_geos(
        projection_type="natural earth", showframe=False, showcoastlines=False,
        showcountries=True, countrycolor="white", countrywidth=0.5,
        showland=True, landcolor=MAP_LAND, showocean=True, oceancolor="white",
        showlakes=False, bgcolor="white", lataxis_range=[-57, 78],
        lonaxis_range=[-170, 55], resolution=110,
    )
    return fig


def colorbar() -> dict:
    return dict(title=None, orientation="h", x=0.5, xanchor="center", y=0,
                yanchor="bottom", len=0.68, thickness=7, tickfont_size=10,
                tickprefix="$", tickformat="~s", outlinewidth=0)


def country_map(df: pd.DataFrame) -> go.Figure:
    if df.empty:
        return empty()
    countries = country_totals(df)
    return map_base(go.Figure(go.Choropleth(
        locations=countries["iso"].tolist(), locationmode="ISO-3",
        z=countries["salesValue"].tolist(), text=countries["Country"].tolist(),
        colorscale=SCALE, zmin=0, zmax=max(float(countries["salesValue"].max()), 1),
        marker_line_color="white", marker_line_width=0.6, colorbar=colorbar(),
        hovertemplate="%{text}<br>Sales: $%{z:,.2f}<extra></extra>",
    )))


def city_map(cities: pd.DataFrame, max_size: int = 5) -> go.Figure:
    mapped = cities.dropna(subset=["latitude", "longitude"])
    if mapped.empty:
        return empty("No mapped cities in this selection.")
    log_sales = np.log1p(mapped["salesValue"])
    sizes = log_sales / log_sales.max() * max_size if log_sales.max() > 0 else np.ones(len(mapped)) * 2
    return map_base(go.Figure(go.Scattergeo(
        lat=mapped["latitude"].tolist(), lon=mapped["longitude"].tolist(), mode="markers",
        text=mapped["City"].tolist(),
        customdata=mapped[["Country", "salesValue", "orders"]].values.tolist(),
        marker=dict(
            size=sizes.tolist(), sizemode="diameter", sizeref=1,
            color=mapped["salesValue"].tolist(), colorscale=SCALE,
            cmin=0, cmax=max(float(mapped["salesValue"].max()), 1), showscale=True,
            colorbar=colorbar(), opacity=0.9, line=dict(width=0.4, color="#444444"),
        ),
        hovertemplate="%{text}, %{customdata[0]}<br>Sales: $%{customdata[1]:,.2f}"
                      "<br>%{customdata[2]} orders<extra></extra>",
    )))


def worker_boxplot(df: pd.DataFrame, workers: list) -> go.Figure:
    if df.empty:
        return empty()
    fig = go.Figure()
    for worker in workers:
        values = df.loc[df["Worker"] == worker, "salesValue"]
        if values.empty:
            continue
        fig.add_trace(go.Box(
            y=values.tolist(), name=str(worker), quartilemethod="linear", boxpoints="outliers",
            fillcolor="#e6e6e6",
            line=dict(color="#737373", width=1.5),
            marker=dict(color="#999999", size=3, opacity=0.6),
            hovertemplate="Salesperson " + str(worker) + "<br>$%{y:,.2f}<extra></extra>",
        ))
    base(fig)
    fig.update_xaxes(title="Salesperson", type="category", categoryorder="array",
                     categoryarray=[str(worker) for worker in workers])
    fig.update_yaxes(title="Order value ($)", tickformat="~s", rangemode="tozero")
    return fig


def traffic_lights(df: pd.DataFrame, workers: list, selected_workers: list) -> go.Figure:
    """Pixel-sized Scatter markers stay circular independent of axis aspect ratio."""
    totals = employee_totals(df, workers)
    fig = base(go.Figure(), height=220)
    for i, row in totals.iterrows():
        worker, sales, orders = int(row["Worker"]), float(row["salesValue"]), int(row["orders"])
        status = employee_status(sales, orders)
        filtered_out = worker not in selected_workers
        active = None if orders == 0 else (0 if sales < 100_000 else 1 if sales <= 150_000 else 2)
        palette = [RED, "#e9b500", "#24935e"]
        fig.add_shape(type="rect", x0=i - 0.27, x1=i + 0.27, y0=0.55, y1=3.45,
                      fillcolor="#f4f4f4", line=dict(color="#e5e5e5", width=1), layer="below")
        fig.add_trace(go.Scatter(
            x=[i, i, i], y=[3, 2, 1], mode="markers",
            marker=dict(symbol="circle", size=20,
                        color=[palette[j] if active == j else "#dedede" for j in range(3)],
                        line=dict(color="white", width=1.5)),
            hovertemplate=f"Salesperson {worker}<br>${sales:,.2f}<br>{orders} orders<br>{status}<extra></extra>",
            showlegend=False,
        ))
        for y, text, size, color in [
            (4.65, f"Salesperson {worker}", 12, "#707070"),
            (4.0, f"<b>${sales:,.0f}</b>", 16, INK),
            (0.02, "Filtered out" if filtered_out else status, 10, "#777777"),
        ]:
            fig.add_annotation(x=i, y=y, text=text, showarrow=False,
                               font=dict(size=size, color=color), xanchor="center")
    fig.update_layout(margin=dict(l=12, r=12, t=4, b=4), hovermode="closest")
    fig.update_xaxes(visible=False, range=[-0.5, len(workers) - 0.5], fixedrange=True)
    fig.update_yaxes(visible=False, range=[-0.4, 5.1], fixedrange=True)
    return fig
