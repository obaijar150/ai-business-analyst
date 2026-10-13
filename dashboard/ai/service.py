import math
from pathlib import Path

import pandas as pd
from django.core.exceptions import ValidationError

from dashboard.ai.providers.base import AnalysisProviderError
from dashboard.ai.providers.factory import get_analysis_provider


OPERATIONS = {"top_groups", "aggregate", "describe", "count_rows", "unsupported"}
AGGREGATIONS = {"sum", "count", "mean", "median", "min", "max"}
NUMERIC_AGGREGATIONS = {"sum", "mean", "median"}


def _json_safe(value):
    if value is None or pd.isna(value):
        return None
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _display_value(value):
    value = _json_safe(value)
    if value is None:
        return "missing"
    if isinstance(value, (int, float)):
        return f"{value:,}"
    return str(value)


def _read_dataset(dataset):
    extension = Path(dataset.file.name).suffix.lower()
    try:
        dataset.file.open("rb")
        if extension == ".csv":
            frame = pd.read_csv(dataset.file)
        elif extension in {".xlsx", ".xls"}:
            frame = pd.read_excel(dataset.file)
        else:
            raise AnalysisProviderError("This dataset file type is not supported for analysis.")
        frame.columns = [str(column) for column in frame.columns]
        return frame
    except Exception as error:
        raise AnalysisProviderError("The stored dataset could not be read. Re-upload the file and try again.") from error
    finally:
        dataset.file.close()


def _validate_plan(plan, frame):
    if not isinstance(plan, dict):
        raise AnalysisProviderError("The AI returned an invalid analysis plan. Please try rephrasing your question.")

    operation = plan.get("operation")
    if operation not in OPERATIONS:
        raise AnalysisProviderError("The AI selected an unsupported analysis. Try asking for a summary, total, or ranking.")
    if operation == "unsupported":
        return {"operation": operation}

    aggregation = plan.get("aggregation", "count")
    if aggregation not in AGGREGATIONS:
        raise AnalysisProviderError("The AI selected an unsupported calculation. Please rephrase your question.")

    group_by = plan.get("group_by")
    value_column = plan.get("value_column")
    if operation == "top_groups":
        if group_by not in frame.columns:
            raise AnalysisProviderError("I couldn't identify a valid grouping column. Please name the column to group by.")
        if value_column is not None and value_column not in frame.columns:
            raise AnalysisProviderError("I couldn't identify a valid value column. Please clarify which column to calculate.")
        if value_column is None and aggregation != "count":
            raise AnalysisProviderError("Counting rows requires a count calculation. Please rephrase your question.")
    elif operation in {"aggregate", "describe"}:
        if value_column not in frame.columns:
            raise AnalysisProviderError("I couldn't identify a valid value column. Please name the column to analyze.")
    if operation == "describe" and not pd.api.types.is_numeric_dtype(frame[value_column]):
        raise AnalysisProviderError(f"The selected column, {value_column}, is not numeric, so I can't calculate its statistics.")
    if operation in {"aggregate", "top_groups"} and value_column is not None:
        if aggregation in NUMERIC_AGGREGATIONS and not pd.api.types.is_numeric_dtype(frame[value_column]):
            raise AnalysisProviderError(f"The selected column, {value_column}, is not numeric for a {aggregation} calculation.")

    try:
        limit = int(plan.get("limit", 5))
    except (TypeError, ValueError) as error:
        raise AnalysisProviderError("The AI returned an invalid result limit. Please try again.") from error
    if not 1 <= limit <= 10:
        limit = 5
    order = "asc" if plan.get("order") == "asc" else "desc"
    return {
        "operation": operation,
        "aggregation": aggregation,
        "group_by": group_by,
        "value_column": value_column,
        "limit": limit,
        "order": order,
    }


def _execute_plan(plan, frame):
    operation = plan["operation"]
    if operation == "count_rows":
        row_count = int(len(frame))
        return {
            "columns": ["Rows"],
            "rows": [[row_count]],
            "columns_used": [],
            "explanation": f"Counted every record in the dataset: {_display_value(row_count)} rows.",
        }

    if operation == "top_groups":
        group_column = plan["group_by"]
        value_column = plan["value_column"]
        aggregation = plan["aggregation"]
        grouped = frame.groupby(group_column, dropna=False, sort=False)
        values = grouped.size() if value_column is None else grouped[value_column].agg(aggregation)
        ranked = values.sort_values(ascending=plan["order" ] == "asc", kind="stable").head(plan["limit"])
        value_label = "Rows" if value_column is None else f"{aggregation.title()} of {value_column}"
        rows = [[_json_safe(index), _json_safe(value)] for index, value in ranked.items()]
        direction = "lowest to highest" if plan["order"] == "asc" else "highest to lowest"
        measure = "row count" if value_column is None else f"{aggregation} of {value_column}"
        if rows:
            rank_word = "lowest" if plan["order"] == "asc" else "highest"
            explanation = (
                f"{_display_value(rows[0][0])} ranks {rank_word} for {measure}, "
                f"with a calculated value of {_display_value(rows[0][1])}. "
                f"I grouped all dataset rows by {group_column} and ranked the groups from {direction}."
            )
        else:
            explanation = f"There are no rows to rank by {group_column}."
        return {
            "columns": [str(group_column), value_label],
            "rows": rows,
            "columns_used": [str(group_column)] + ([str(value_column)] if value_column is not None else []),
            "explanation": explanation,
        }

    value_column = plan["value_column"]
    aggregation = plan["aggregation"]
    if operation == "aggregate":
        series = frame[value_column]
        value = int(series.count()) if aggregation == "count" else series.agg(aggregation)
        exact_value = _display_value(value)
        return {
            "columns": ["Column", "Calculation", "Result"],
            "rows": [[str(value_column), aggregation.title(), _json_safe(value)]],
            "columns_used": [str(value_column)],
            "explanation": f"The {aggregation} of {value_column} is {exact_value}, calculated from the dataset values.",
        }

    series = frame[value_column].dropna()
    stats = {
        "Count": int(series.count()),
        "Mean": _json_safe(series.mean()),
        "Median": _json_safe(series.median()),
        "Standard deviation": _json_safe(series.std()),
        "Minimum": _json_safe(series.min()),
        "Maximum": _json_safe(series.max()),
    }
    summary = (
        f"For {value_column}, the mean is {_display_value(stats['Mean'])}, "
        f"the median is {_display_value(stats['Median'])}, and the range is "
        f"{_display_value(stats['Minimum'])} to {_display_value(stats['Maximum'])}. "
        "These statistics use its non-empty numeric values."
    )
    return {
        "columns": ["Statistic", str(value_column)],
        "rows": [[label, value] for label, value in stats.items()],
        "columns_used": [str(value_column)],
        "explanation": summary,
    }


def analyze_dataset(dataset, question, provider=None):
    frame = _read_dataset(dataset)
    schema = [{"name": str(name), "data_type": str(frame[name].dtype)} for name in frame.columns]
    ai_provider = provider or get_analysis_provider()
    plan = ai_provider.create_plan(question=question, schema=schema)
    valid_plan = _validate_plan(plan, frame)
    if valid_plan["operation"] == "unsupported":
        return {
            "dataset": {"id": dataset.pk, "name": dataset.name},
            "question": question,
            "answer": "I couldn't map that question to a supported dataset calculation yet. Try asking for a total, average, descriptive statistics, row count, or a ranking by category.",
            "analysis": {"operation": "unsupported", "columns_used": []},
            "result": {"columns": [], "rows": []},
        }

    executed = _execute_plan(valid_plan, frame)
    return {
        "dataset": {"id": dataset.pk, "name": dataset.name},
        "question": question,
        "answer": executed.pop("explanation"),
        "analysis": {
            "operation": valid_plan["operation"],
            "columns_used": executed.pop("columns_used"),
            "aggregation": valid_plan.get("aggregation"),
        },
        "result": executed,
    }
