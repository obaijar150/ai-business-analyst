import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings

from .base import AnalysisProvider, AnalysisProviderError


class GeminiAnalysisProvider(AnalysisProvider):
    endpoint = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, api_key=None, model=None, timeout=45):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_MODEL
        self.timeout = timeout

    def create_plan(self, question, schema):
        if not self.api_key:
            raise AnalysisProviderError(
                "Gemini is not configured. Create a free API key in Google AI Studio, add GEMINI_API_KEY to .env, and restart the server."
            )

        system_prompt = (
            "You are an AI business analyst planner. Choose a safe, simple analysis plan for the user's question. "
            "You receive column names and data types only. Never calculate or claim numerical results. Never write code. "
            "Only choose columns present in the supplied schema. If the question cannot be answered with the supported "
            "operations, use operation unsupported. Return one JSON object with keys: operation, group_by, value_column, "
            "aggregation, order, limit, chart. Supported operations: top_groups, aggregate, describe, count_rows, unsupported. "
    "chart is optional and may be one of bar, line, pie, scatter with keys type, x, y, title, or null. "
            "Supported aggregations: sum, count, mean, median, min, max. order is desc or asc. limit is an integer from 1 to 10. "
            "For top_groups, group_by is required and value_column may be null only for counting rows per group. "
            "For aggregate and describe, value_column is required. For count_rows, both columns are null."
        )
        prompt = json.dumps({"question": question, "columns": schema}, ensure_ascii=False)
        payload = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "temperature": 0.1,
                "maxOutputTokens": 400,
            },
        }
        request = Request(
            self.endpoint.format(model=self.model),
            data=json.dumps(payload).encode("utf-8"),
            headers={"x-goog-api-key": self.api_key, "Content-Type": "application/json"},
            method="POST",
        )
        transient_http_statuses = {429, 500, 502, 503, 504}
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                with urlopen(request, timeout=self.timeout) as response:
                    completion = json.loads(response.read().decode("utf-8"))
                content = completion["candidates"][0]["content"]["parts"][0]["text"]
                plan = json.loads(content)
                break
            except HTTPError as error:
                if error.code in transient_http_statuses and attempt < max_attempts - 1:
                    time.sleep(1 + attempt)
                    continue
                if error.code == 429:
                    message = "Gemini's free-tier rate limit was reached. Wait a moment and retry, or check your Google AI Studio usage limits."
                elif error.code in {401, 403}:
                    message = "Gemini rejected this API key or its permissions. Check that the key is valid and restricted to the Gemini API."
                elif error.code == 400:
                    message = "Gemini could not process this request. Check the configured model and try again."
                elif error.code == 503:
                    message = "Gemini is temporarily unavailable due to high demand. Wait 10-30 seconds and retry."
                elif error.code in {500, 502, 504}:
                    message = "Gemini is temporarily unavailable. Try again in a moment."
                else:
                    message = "Gemini could not process this request. Check the API key, model, and Google AI Studio project settings."
                raise AnalysisProviderError(message) from error
            except (URLError, TimeoutError) as error:
                if attempt < max_attempts - 1:
                    time.sleep(1 + attempt)
                    continue
                raise AnalysisProviderError("Could not reach the Gemini API. Try again in a moment.") from error
            except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
                raise AnalysisProviderError("Gemini returned an unreadable analysis plan. Please rephrase your question.") from error

        if not isinstance(plan, dict):
            raise AnalysisProviderError("Gemini returned an invalid analysis plan. Please rephrase your question.")
        return plan
