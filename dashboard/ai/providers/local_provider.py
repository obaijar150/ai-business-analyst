"""A dependency-free analyst that turns common questions into analysis plans."""

import re

from .base import AnalysisProvider, AnalysisProviderError


_STOP_WORDS = {
    "a", "an", "the", "of", "for", "to", "in", "on", "by", "and", "or",
    "is", "are", "was", "were", "what", "which", "who", "how", "many",
    "much", "show", "me", "give", "get", "please", "with", "from",
}


def _normalize(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()


def _tokens(value):
    return {token for token in _normalize(value).split() if token and token not in _STOP_WORDS}


def _is_numeric(dtype):
    dtype = str(dtype).lower()
    return any(marker in dtype for marker in ("int", "float", "double", "decimal", "number"))


def _explicit_columns(question, columns):
    normalized_question = _normalize(question)
    mentioned = []
    for column in columns:
        normalized_column = _normalize(column["name"])
        if normalized_column and normalized_column in normalized_question:
            mentioned.append(column["name"])
    return mentioned


def _best_column(question, columns, numeric=None):
    candidates = [column for column in columns if _is_numeric(column["data_type"]) == bool(numeric)] if numeric is not None else list(columns)
    if not candidates:
        return None
    mentioned = _explicit_columns(question, candidates)
    if mentioned:
        return mentioned[0]
    question_tokens = _tokens(question)
    best = None
    best_score = 0
    for column in candidates:
        score = len(_tokens(column["name"]) & question_tokens)
        if score > best_score:
            best, best_score = column["name"], score
    return best


class LocalAnalysisProvider(AnalysisProvider):
    """Plan analyses from question keywords without calling an external LLM."""

    def create_plan(self, question, schema):
        if not isinstance(schema, list):
            raise AnalysisProviderError("The dataset schema could not be inspected.")

        columns = [item for item in schema if isinstance(item, dict) and item.get("name")]
        if not columns:
            raise AnalysisProviderError("The dataset has no columns to analyze.")

        normalized_question = _normalize(question)
        numeric_columns = [column for column in columns if _is_numeric(column["data_type"])]
        categorical_columns = [column for column in columns if not _is_numeric(column["data_type"])]

        count_intent = (
            "how many" in normalized_question
            or "count" in normalized_question
            or "number of" in normalized_question
            or "records" in normalized_question
            or "rows" in normalized_question
        )
        describe_intent = any(word in normalized_question for word in ("describe", "summary", "statistics", "stats", "distribution", "profile"))
        top_intent = any(word in normalized_question for word in ("top", "best", "highest", "largest", "biggest", "most", "greatest"))
        bottom_intent = any(word in normalized_question for word in ("bottom", "lowest", "smallest", "worst", "least"))
        aggregate_intent = any(word in normalized_question for word in ("total", "sum", "average", "mean", "median", "minimum", "maximum", "min", "max"))
        ranking_intent = top_intent or bottom_intent

        match = re.search(r"\b(?:top|limit)\s+(\d{1,2})\b", normalized_question)
        limit = int(match.group(1)) if match else 5
        limit = min(max(limit, 1), 10)

        if ranking_intent and categorical_columns:
            group_by = _best_column(question, categorical_columns)
            mentioned_numeric = _explicit_columns(question, numeric_columns)
            count_group = (
                "count" in normalized_question
                or "how many" in normalized_question
                or "number of" in normalized_question
                or not mentioned_numeric and not numeric_columns
            )
            if count_group and mentioned_numeric == []:
                # Count rows per group unless a numeric measure is named.
                if not any(word in normalized_question for word in ("revenue", "sales", "units", "amount", "price", "cost", "value")):
                    count_group = True
            value_column = None if count_group and not mentioned_numeric else (mentioned_numeric[0] if mentioned_numeric else (numeric_columns[0]["name"] if numeric_columns and not count_group else None))
            # Keep an explicitly named numeric measure even when count words appear.
            if mentioned_numeric:
                value_column = mentioned_numeric[0]
            if value_column is None:
                aggregation = "count"
            elif any(word in normalized_question for word in ("average", "mean")):
                aggregation = "mean"
            else:
                aggregation = "sum"
            return {
                "operation": "top_groups",
                "group_by": group_by,
                "value_column": value_column,
                "aggregation": aggregation,
                "order": "asc" if bottom_intent else "desc",
                "limit": limit,
            }

        if describe_intent and numeric_columns:
            value_column = _best_column(question, numeric_columns, numeric=True)
            if value_column is None:
                value_column = numeric_columns[0]["name"]
            return {
                "operation": "describe",
                "group_by": None,
                "value_column": value_column,
                "aggregation": "count",
                "order": "desc",
                "limit": limit,
            }

        if count_intent and not aggregate_intent and not numeric_columns:
            return {
                "operation": "count_rows",
                "group_by": None,
                "value_column": None,
                "aggregation": "count",
                "order": "desc",
                "limit": limit,
            }

        if (count_intent or aggregate_intent) and numeric_columns:
            mentioned_numeric = _explicit_columns(question, numeric_columns)
            if any(word in normalized_question for word in ("count", "how many")) and not mentioned_numeric and not any(word in normalized_question for word in ("total", "sum", "average", "mean", "median", "minimum", "maximum", "min", "max", "revenue", "units", "amount", "price", "cost", "value")):
                return {
                    "operation": "count_rows",
                    "group_by": None,
                    "value_column": None,
                    "aggregation": "count",
                    "order": "desc",
                    "limit": limit,
                }
            if any(word in normalized_question for word in ("average", "mean")):
                aggregation = "mean"
            elif any(word in normalized_question for word in ("median",)):
                aggregation = "median"
            elif any(word in normalized_question for word in ("minimum", "min", "lowest")):
                aggregation = "min"
            elif any(word in normalized_question for word in ("maximum", "max", "highest")):
                aggregation = "max"
            elif any(word in normalized_question for word in ("count", "how many")):
                aggregation = "count"
            else:
                aggregation = "sum"
            if len(mentioned_numeric) >= 2:
                value_column = mentioned_numeric
            else:
                value_column = _best_column(question, numeric_columns, numeric=True)
                if value_column is None:
                    value_column = numeric_columns[0]["name"]
            return {
                "operation": "aggregate",
                "group_by": None,
                "value_column": value_column,
                "aggregation": aggregation,
                "order": "desc",
                "limit": limit,
            }

        if count_intent:
            return {
                "operation": "count_rows",
                "group_by": None,
                "value_column": None,
                "aggregation": "count",
                "order": "desc",
                "limit": limit,
            }

        raise AnalysisProviderError(
            "I couldn't map that question to a supported calculation yet. Try asking for a total, average, descriptive statistics, row count, or a ranking by category."
        )
