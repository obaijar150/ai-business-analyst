import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .base import AnalysisProvider, AnalysisProviderError


class OpenAIAnalysisProvider(AnalysisProvider):
    endpoint = "https://api.openai.com/v1/chat/completions"

    def __init__(self, api_key=None, model=None, timeout=30):
        self.api_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_MODEL
        self.timeout = timeout

    def create_plan(self, question, schema):
        if not self.api_key:
            raise AnalysisProviderError(
                "OpenAI is not configured. Add OPENAI_API_KEY to the environment and restart the server."
            )

        system_prompt = (
            "You are an AI business analyst planner. Choose a safe, simple analysis plan for the user's question. "
            "You receive column names and data types only. Never calculate or claim numerical results. Never write code. "
            "Only choose columns present in the supplied schema. If the question cannot be answered with the supported "
            "operations, use operation unsupported. Return one JSON object with keys: operation, group_by, value_column, "
            "aggregation, order, limit. Supported operations: top_groups, aggregate, describe, count_rows, unsupported. "
            "Supported aggregations: sum, count, mean, median, min, max. order is desc or asc. limit is an integer from 1 to 10. "
            "For top_groups, group_by is required and value_column may be null only for counting rows per group. "
            "For aggregate and describe, value_column is required. For count_rows, both columns are null."
        )
        prompt = json.dumps({"question": question, "columns": schema}, ensure_ascii=False)
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "response_format": {"type": "json_object"},
            "max_completion_tokens": 400,
        }
        request = Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                completion = json.loads(response.read().decode("utf-8"))
            content = completion["choices"][0]["message"]["content"]
            plan = json.loads(content)
        except HTTPError as error:
            try:
                provider_error = json.loads(error.read().decode("utf-8")).get("error", {})
                error_code = provider_error.get("code")
            except (AttributeError, UnicodeDecodeError, json.JSONDecodeError):
                error_code = None
            if error_code in {"insufficient_quota", "credit_balance_exhausted", "billing_hard_limit_reached"}:
                message = "OpenAI API credits or the project spending limit are exhausted. Add API credits or increase the project limit, then try again."
            elif error.code == 429:
                message = "OpenAI rate-limited this request. Wait a moment and retry, or check the project's usage limits."
            elif error.code in {401, 403}:
                message = "OpenAI rejected this API key or its permissions. Check the key and its access to the configured model."
            else:
                message = "OpenAI could not process this request. Check the API key, model, and project settings."
            raise AnalysisProviderError(message) from error
        except (URLError, TimeoutError) as error:
            raise AnalysisProviderError("Could not reach the OpenAI API. Try again in a moment.") from error
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise AnalysisProviderError("OpenAI returned an unreadable analysis plan. Please rephrase your question.") from error

        if not isinstance(plan, dict):
            raise AnalysisProviderError("OpenAI returned an invalid analysis plan. Please rephrase your question.")
        return plan
