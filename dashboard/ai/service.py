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
        if isinstance(value_column, list):
            if not value_column or any(column not in frame.columns for column in value_column):
                raise AnalysisProviderError("I couldn't identify a valid value column. Please name the column to analyze.")
        elif value_column not in frame.columns:
            raise AnalysisProviderError("I couldn't identify a valid value column. Please name the column to analyze.")
    if operation == "describe" and not isinstance(value_column, list) and not pd.api.types.is_numeric_dtype(frame[value_column]):
        raise AnalysisProviderError(f"The selected column, {value_column}, is not numeric, so I can't calculate its statistics.")
    if operation in {"aggregate", "top_groups"} and value_column is not None:
        if isinstance(value_column, list):
            if aggregation in NUMERIC_AGGREGATIONS and any(not pd.api.types.is_numeric_dtype(frame[column]) for column in value_column):
                raise AnalysisProviderError("One of the selected columns is not numeric for this calculation.")
        elif aggregation in NUMERIC_AGGREGATIONS and not pd.api.types.is_numeric_dtype(frame[value_column]):
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
        value_columns = value_column if isinstance(value_column, list) else [value_column]
        rows = []
        columns_used = []
        values = {}
        for column in value_columns:
            series = frame[column]
            value = int(series.count()) if aggregation == "count" else series.agg(aggregation)
            values[str(column)] = value
            rows.append([str(column), aggregation.title(), _json_safe(value)])
            columns_used.append(str(column))
        if len(value_columns) == 1:
            exact_value = _display_value(values[str(value_columns[0])])
            explanation = f"The {aggregation} of {value_columns[0]} is {exact_value}, calculated from the dataset values."
        else:
            explanation = "; ".join(
                f"the {aggregation} of {column} is {_display_value(values[str(column)])}"
                for column in value_columns
            ).capitalize() + ", calculated from the dataset values."
        return {
            "columns": ["Column", "Calculation", "Result"],
            "rows": rows,
            "columns_used": columns_used,
            "explanation": explanation,
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


def _build_evidence(dataset, frame, plan, result):
    """Describe only the source rows and calculations that produced this result."""
    operation = plan["operation"]
    rows_examined = int(len(frame))
    facts = [f"Dataset: {dataset.name}", f"Rows examined: {rows_examined}"]

    if operation == "count_rows":
        formula = "count(dataset rows)"
        values_used = rows_examined
        interpretation = "This is the number of records present in the uploaded dataset."
    elif operation == "top_groups":
        group_by = plan["group_by"]
        value_column = plan["value_column"]
        aggregation = plan["aggregation"]
        if value_column is None:
            formula = f"count(rows) grouped by {group_by}"
            values_used = rows_examined
            measure = "row count"
        else:
            values_used = int(frame[value_column].count())
            formula = f"{aggregation}({value_column}) grouped by {group_by}"
            measure = f"{aggregation} of {value_column}"
        if result["rows"]:
            ranked_value = result["rows"][0][0]
            direction = "lowest" if plan["order"] == "asc" else "highest"
            interpretation = (
                f"Within this dataset, {_display_value(ranked_value)} ranks {direction} by {measure}. "
                "This describes the calculated ranking and does not establish its cause."
            )
        else:
            interpretation = f"No groups were available to rank by {group_by}."
    elif operation == "aggregate":
        value_column = plan["value_column"]
        aggregation = plan["aggregation"]
        value_columns = value_column if isinstance(value_column, list) else [value_column]
        values_used = int(frame[value_columns[0]].count())
        formula = ", ".join(f"{aggregation}({column})" for column in value_columns) + " over non-missing values"
        interpretation = (
            f"This value summarizes {value_column} using {aggregation}; "
            "it does not by itself establish a trend or cause."
        )
    else:
        value_column = plan["value_column"]
        values_used = int(frame[value_column].count())
        formula = f"count, mean, median, standard deviation, minimum, and maximum of {value_column}"
        interpretation = (
            f"These statistics describe the non-missing numeric values in {value_column}; "
            "they do not explain causes or predict future values."
        )

    return {
        "dataset": dataset.name,
        "period": "All dataset rows; no period filter was applied.",
        "rows_examined": rows_examined,
        "fact": facts,
        "calculation": [f"Formula: {formula}", f"Non-missing values used: {values_used}"],
        "interpretation": [interpretation],
        "recommendation": ["No recommendation was generated."],
    }


def analyze_dataset(dataset, question, provider=None):
    frame = _read_dataset(dataset)
    schema = [{"name": str(name), "data_type": str(frame[name].dtype)} for name in frame.columns]
    ai_provider = provider or get_analysis_provider()
    plan = ai_provider.create_plan(question=question, schema=schema)
    valid_plan = _validate_plan(plan, frame)
    if valid_plan["operation"] == "unsupported":
        explanation = "I couldn't map that question to a supported dataset calculation yet. Try asking for a total, average, descriptive statistics, row count, or a ranking by category."
        analysis = {"operation": "unsupported", "columns_used": []}
        result = {"columns": [], "rows": []}
        evidence = {
            "dataset": dataset.name,
            "period": "No period filter was applied.",
            "rows_examined": None,
            "fact": ["No dataset calculation was performed."],
            "calculation": ["No supported calculation was selected."],
            "interpretation": ["The question could not be mapped to a supported calculation."],
            "recommendation": ["No recommendation was generated."],
        }
    else:
        executed = _execute_plan(valid_plan, frame)
        explanation = executed.pop("explanation")
        columns_used = executed.pop("columns_used")
        result = {"columns": executed["columns"], "rows": executed["rows"]}
        analysis = {
            "operation": valid_plan["operation"],
            "columns_used": columns_used,
            "aggregation": valid_plan.get("aggregation"),
        }
        evidence = _build_evidence(dataset, frame, valid_plan, result)

    return {
        "dataset": {"id": dataset.pk, "name": dataset.name},
        "question": question,
        "answer": explanation,
        "explanation": explanation,
        "analysis": analysis,
        "result": result,
        "evidence": evidence,
    }
