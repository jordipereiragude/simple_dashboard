"""Northwind calculations shared by the dashboard and its tests."""
from pathlib import Path
from typing import Iterable, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
WORKBOOK = ROOT / "northwind-en.xlsx"
COORDINATES = ROOT / "data" / "city_coordinates.csv"
SALES_BINS = list(range(0, 5500, 500)) + [float("inf")]
SALES_LABELS = [f"{n:,}–{n + 500:,}" for n in range(0, 5000, 500)] + ["5,000+"]
COUNTRY_ISO = {
    "Argentina": "ARG", "Austria": "AUT", "Belgium": "BEL", "Brazil": "BRA",
    "Canada": "CAN", "Denmark": "DNK", "Finland": "FIN", "France": "FRA",
    "Germany": "DEU", "Ireland": "IRL", "Italy": "ITA", "Mexico": "MEX",
    "Norway": "NOR", "Poland": "POL", "Portugal": "PRT", "Spain": "ESP",
    "Sweden": "SWE", "Switzerland": "CHE", "UK": "GBR", "USA": "USA",
    "Venezuela": "VEN",
}


def load_orders(path: Path = WORKBOOK) -> pd.DataFrame:
    df = pd.read_excel(path)
    required = {"Worker", "Client", "City", "Country", "salesValue"}
    missing = required.difference(df.columns)
    if missing:
        raise ValueError(f"Workbook is missing columns: {', '.join(sorted(missing))}")
    if df[list(required)].isna().any().any():
        raise ValueError("Required workbook columns contain missing values.")
    df["salesValue"] = pd.to_numeric(df["salesValue"], errors="raise")
    if not np.isfinite(df["salesValue"]).all() or (df["salesValue"] < 0).any():
        raise ValueError("Sales values must be finite, nonnegative numbers.")
    if not pd.to_numeric(df["Worker"]).mod(1).eq(0).all():
        raise ValueError("Salesperson identifiers must be whole numbers.")
    df["Worker"] = df["Worker"].astype(int)
    return df


def filter_orders(df: pd.DataFrame, workers: Iterable[int], countries: Iterable[str],
                  value_range: Tuple[float, float]) -> pd.DataFrame:
    """All filters intersect; the order-value endpoints are inclusive."""
    return df.loc[
        df["Worker"].isin(workers)
        & df["Country"].isin(countries)
        & df["salesValue"].between(*value_range, inclusive="both")
    ].copy()


def summary(df: pd.DataFrame) -> dict:
    return {
        "sales": float(df["salesValue"].sum()),
        "orders": len(df),
        "customers": int(df["Client"].nunique()),
        "median": None if df.empty else float(df["salesValue"].median()),
        "countries": int(df["Country"].nunique()),
    }


def ranking(df: pd.DataFrame, column: str, limit: Optional[int] = None) -> pd.DataFrame:
    result = df.groupby(column, observed=True)["salesValue"].sum().reset_index()
    result = result.sort_values(["salesValue", column], ascending=[False, True]).reset_index(drop=True)
    return result.head(limit) if limit is not None else result


def sales_histogram(df: pd.DataFrame) -> Tuple[pd.Series, Optional[str]]:
    """Match notebook cell 14's left-closed $500 bins, including 5000 in the tail."""
    cut = pd.cut(df["salesValue"], SALES_BINS, labels=SALES_LABELS, right=False)
    counts = cut.value_counts(sort=False).reindex(SALES_LABELS, fill_value=0)
    mean = df["salesValue"].mean()
    mean_bin = None
    if pd.notna(mean):
        mean_bin = SALES_LABELS[int(np.searchsorted(SALES_BINS, mean, side="right") - 1)]
    return counts, mean_bin


def customer_frequency(df: pd.DataFrame) -> pd.Series:
    """Distribution of customers by their number of orders (one row = one order)."""
    counts = df.groupby("Client", observed=True).size()
    if counts.empty:
        return pd.Series(dtype="int64")
    return counts.value_counts().reindex(range(1, int(counts.max()) + 1), fill_value=0).sort_index()


def country_totals(df: pd.DataFrame) -> pd.DataFrame:
    result = ranking(df, "Country")
    total = result["salesValue"].sum()
    result["share"] = result["salesValue"] / total * 100 if total > 0 else 0.0
    result["cumulative"] = result["share"].cumsum()
    result["iso"] = result["Country"].map(COUNTRY_ISO)
    return result


def employee_totals(df: pd.DataFrame, workers: Iterable[int]) -> pd.DataFrame:
    return df.groupby("Worker", observed=True).agg(
        salesValue=("salesValue", "sum"), orders=("salesValue", "size")
    ).reindex(list(workers), fill_value=0).reset_index()


def employee_status(sales: float, orders: int) -> str:
    if orders == 0:
        return "No orders"
    if sales < 100_000:
        return "Below $100k"
    if sales <= 150_000:
        return "$100k–$150k"
    return "Above $150k"


def city_totals(df: pd.DataFrame, coordinates: Optional[pd.DataFrame] = None) -> pd.DataFrame:
    if coordinates is None:
        coordinates = pd.read_csv(COORDINATES)
    result = df.groupby(["City", "Country"], observed=True).agg(
        salesValue=("salesValue", "sum"), orders=("salesValue", "size")
    ).reset_index()
    return result.merge(coordinates, on=["City", "Country"], how="left", validate="one_to_one")
