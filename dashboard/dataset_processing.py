import math
from pathlib import Path

import pandas as pd
from django.core.exceptions import ValidationError


ALLOWED_EXTENSIONS = {".csv", ".xlsx", ".xls"}
MAX_FILE_SIZE = 25 * 1024 * 1024


def _json_value(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def inspect_dataset(upload):
    extension = Path(upload.name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Upload a CSV or Excel file (.csv, .xlsx, or .xls).")
    if upload.size > MAX_FILE_SIZE:
        raise ValidationError("Files must be 25 MB or smaller.")

    try:
        upload.seek(0)
        if extension == ".csv":
            frame = pd.read_csv(upload)
        else:
            frame = pd.read_excel(upload)
    except Exception as error:
        raise ValidationError("The file could not be read. Check that it is a valid CSV or Excel file.") from error
    finally:
        upload.seek(0)

    columns = []
    for name in frame.columns:
        series = frame[name]
        columns.append({
            "name": str(name),
            "data_type": str(series.dtype),
            "missing_values": int(series.isna().sum()),
            "unique_values": int(series.nunique(dropna=True)),
        })

    numeric = frame.select_dtypes(include="number")
    numeric_stats = {}
    for name in numeric.columns:
        series = numeric[name].dropna()
        numeric_stats[str(name)] = {
            "count": int(series.count()),
            "mean": _json_value(series.mean()),
            "median": _json_value(series.median()),
            "std": _json_value(series.std()),
            "min": _json_value(series.min()),
            "max": _json_value(series.max()),
        }

    preview = []
    for row in frame.head(20).itertuples(index=False, name=None):
        preview.append({str(name): _json_value(value) for name, value in zip(frame.columns, row)})

    return {
        "file_type": extension.lstrip("."),
        "row_count": int(len(frame)),
        "column_count": int(len(frame.columns)),
        "columns": columns,
        "statistics": {
            "missing_values": int(frame.isna().sum().sum()),
            "numeric_columns": int(len(numeric.columns)),
            "numeric": numeric_stats,
        },
        "metadata": {
            "preview": preview,
            "preview_limit": 20,
            "source_filename": upload.name,
            "file_size_bytes": upload.size,
        },
    }
