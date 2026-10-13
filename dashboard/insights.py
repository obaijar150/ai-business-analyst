import math
from pathlib import Path

import pandas as pd

from dashboard.ai.providers.base import AnalysisProviderError


def _read_dataset(dataset):
    extension = Path(dataset.file.name).suffix.lower()
    dataset.file.open("rb")
    try:
        if extension == ".csv":
            frame = pd.read_csv(dataset.file)
        elif extension in {".xlsx", ".xls"}:
            frame = pd.read_excel(dataset.file)
        else:
            raise AnalysisProviderError("This dataset file type is not supported.")
    finally:
        dataset.file.close()
    frame.columns = [str(column) for column in frame.columns]
    return frame


def _is_date(name, dtype):
    return "date" in str(dtype).lower() or "date" in str(name).lower() or "time" in str(name).lower()


def _numeric_columns(frame):
    return [column for column in frame.columns if pd.api.types.is_numeric_dtype(frame[column])]


def _measure(frame, numeric_columns):
    for preferred in ("revenue", "sales", "amount", "profit", "value", "total"):
        for column in numeric_columns:
            if preferred in column.lower():
                return column
    return numeric_columns[0] if numeric_columns else None


def _category_column(frame):
    for column in frame.columns:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            name = column.lower()
            if any(word in name for word in ("product", "category", "item", "name")):
                return column
    for column in frame.columns:
        if not pd.api.types.is_numeric_dtype(frame[column]):
            return column
    return None


def _date_column(frame):
    for column in frame.columns:
        if _is_date(column, frame[column].dtype):
            return column
    return None


def generate_insights(dataset):
    frame = _read_dataset(dataset)
    numeric_columns = _numeric_columns(frame)
    measure = _measure(frame, numeric_columns)
    category_column = _category_column(frame)
    date_column = _date_column(frame)

    kpis = [{"label": "Rows", "value": int(len(frame))}]
    if measure is not None:
        series = frame[measure]
        kpis.extend([
            {"label": f"Total {measure}", "value": _safe(series.sum())},
            {"label": f"Average {measure}", "value": _safe(series.mean())},
            {"label": f"Maximum {measure}", "value": _safe(series.max())},
            {"label": f"Minimum {measure}", "value": _safe(series.min())},
        ])

    top_products = []
    worst_products = []
    if category_column is not None and measure is not None:
        grouped = frame.groupby(category_column, dropna=False)[measure].sum().sort_values(ascending=False)
        top_products = [{"name": str(index), "value": _safe(value)} for index, value in grouped.head(5).items()]
        worst_products = [{"name": str(index), "value": _safe(value)} for index, value in grouped.tail(5).sort_values().items()]

    trends = {"labels": [], "values": []}
    if date_column is not None and measure is not None:
        monthly = frame.copy()
        monthly["__month"] = pd.to_datetime(monthly[date_column], errors="coerce").dt.strftime("%Y-%m")
        trend_values = monthly.groupby("__month", dropna=True)[measure].sum().sort_index()
        trends = {"labels": list(trend_values.index), "values": [_safe(value) for value in trend_values.tolist()]}

    anomalies = []
    if measure is not None:
        anomalies = _detect_anomalies(frame, measure, date_column)

    forecast = None
    if trends["values"]:
        forecast = _forecast(trends["labels"], trends["values"])

    recommendations = _recommendations(measure, top_products, worst_products, anomalies, trends, frame)

    charts = []
    if top_products:
        charts.append({"type": "bar", "x": "name", "y": "value", "title": f"Top {category_column or 'groups'} by {measure}", "data": top_products})
    if trends["labels"]:
        charts.append({"type": "line", "labels": trends["labels"], "values": trends["values"], "title": f"{measure} trend"})
    if kpis:
        pass

    return {
        "dataset": {"id": dataset.pk, "name": dataset.name, "row_count": len(frame), "column_count": len(frame.columns)},
        "measure": measure,
        "kpis": kpis,
        "top_products": top_products,
        "worst_products": worst_products,
        "trends": trends,
        "anomalies": anomalies,
        "forecast": forecast,
        "recommendations": recommendations,
        "charts": charts,
    }


def _safe(value):
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _detect_anomalies(frame, measure, date_column):
    series = frame[measure]
    if len(series) < 5:
        return []
    mean = series.mean()
    std = series.std()
    if not std or pd.isna(std) or std == 0:
        return []
    anomalies = []
    if date_column is not None:
        # Report monthly totals that are unusually high or low.
        monthly = frame.copy()
        monthly["__month"] = pd.to_datetime(monthly[date_column], errors="coerce").dt.strftime("%Y-%m")
        monthly_totals = monthly.groupby("__month")[measure].sum()
        m_mean = monthly_totals.mean()
        m_std = monthly_totals.std()
        if m_std and not pd.isna(m_std) and m_std != 0:
            for month, value in monthly_totals.items():
                z = (value - m_mean) / m_std
                if abs(z) >= 2:
                    anomalies.append({
                        "period": str(month),
                        "measure": measure,
                        "value": _safe(value),
                        "reason": "Unusually high" if z > 0 else "Unusually low",
                    })
    # Record-level outliers
    z_values = (series - mean) / std
    outlier_indices = list(z_values[abs(z_values) >= 3].index)
    for index in outlier_indices[:10]:
        anomalies.append({
            "row": int(index) + 1,
            "measure": measure,
            "value": _safe(series.loc[index]),
            "reason": "Extreme value",
        })
    return anomalies


def _forecast(labels, values):
    if len(values) < 2:
        return None
    last_value = values[-1]
    average = sum(values) / len(values)
    trend_change = values[-1] - values[0]
    projected = last_value + (trend_change / (len(values) - 1))
    next_label = _next_period(labels[-1])
    return {"period": next_label, "value": _safe(projected), "method": "linear trend"}


def _next_period(label):
    try:
        period = pd.Period(label, freq="M")
        return str(period + 1)
    except (ValueError, TypeError):
        return f"Next period after {label}"


def _recommendations(measure, top_products, worst_products, anomalies, trends, frame):
    recommendations = []
    if top_products:
        recommendations.append(f"Focus on {top_products[0]['name']}, the top performer by {measure}.")
    if worst_products:
        recommendations.append(f"Review {worst_products[0]['name']}, which has the lowest {measure}.")
    if anomalies:
        recommendations.append("Investigate the detected anomalies before making decisions.")
    if trends["values"] and len(trends["values"]) >= 2:
        if trends["values"][-1] > trends["values"][0]:
            recommendations.append(f"{measure.title()} is trending upward; consider scaling successful activities.")
        else:
            recommendations.append(f"{measure.title()} is trending downward; review pricing, marketing, or supply constraints.")
    if not recommendations:
        recommendations.append("Collect more detailed data to generate stronger business recommendations.")
    return recommendations