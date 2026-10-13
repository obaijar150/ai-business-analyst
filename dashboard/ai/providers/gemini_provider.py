import json
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
            "aggregation, order, limit. Supported operations: top_groups, aggregate, describe, count_rows, unsupported. "
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
        try:
            with urlopen(request, timeout=self.timeout) as response:
                completion = json.loads(response.read().decode("utf-8"))
            content = completion["candidates"][0]["content"]["parts"][0]["text"]
            plan = json.loads(content)
        except HTTPError as error:
            if error.code == 429:
                message = "Gemini's free-tier rate limit was reached. Wait a moment and retry, or check your Google AI Studio usage limits."
            elif error.code in {401, 403}:
                message = "Gemini rejected this API key or its permissions. Check that the key is valid and restricted to the Gemini API."
            elif error.code == 400:
                message = "Gemini could not process this request. Check the configured model and try again."
            else:
                message = "Gemini could not process this request. Check the API key, model, and Google AI Studio project settings."
            raise AnalysisProviderError(message) from error
        except (URLError, TimeoutError) as error:
            raise AnalysisProviderError("Could not reach the Gemini API. Try again in a moment.") from error
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise AnalysisProviderError("Gemini returned an unreadable analysis plan. Please rephrase your question.") from error

        if not isinstance(plan, dict):
            raise AnalysisProviderError("Gemini returned an invalid analysis plan. Please rephrase your question.")
        return plan
