import json
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.test import override_settings
from rest_framework.test import APIClient

from dashboard.ai.providers.base import AnalysisProviderError
from dashboard.ai.providers.gemini_provider import GeminiAnalysisProvider
from dashboard.ai.providers.openai_provider import OpenAIAnalysisProvider
from dashboard.models import Dataset


User = get_user_model()


class PlannedProvider:
    def __init__(self, plan):
        self.plan = plan
        self.seen_schema = None

    def create_plan(self, question, schema):
        self.seen_schema = schema
        return self.plan


def create_dataset(user):
    return Dataset.objects.create(
        owner=user,
        name="Product sales",
        file=SimpleUploadedFile(
            "sales.csv",
            b"product,units,revenue\nWidget,2,20\nGadget,4,50\nWidget,3,30\n",
            content_type="text/csv",
        ),
        file_type="csv",
        row_count=3,
        column_count=3,
    )


@pytest.mark.django_db
def test_analyze_api_uses_llm_plan_and_returns_computed_group_totals(monkeypatch):
    user = User.objects.create_user(username="analyst", password="Strong-pass-209!")
    dataset = create_dataset(user)
    provider = PlannedProvider({
        "operation": "top_groups",
        "group_by": "product",
        "value_column": "units",
        "aggregation": "sum",
        "order": "desc",
        "limit": 5,
    })
    monkeypatch.setattr("dashboard.ai.service.get_analysis_provider", lambda: provider)
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(reverse("api_analyze"), {
        "dataset_id": str(dataset.pk),
        "question": "What are the best selling products?",
    }, format="json")

    assert response.status_code == 200
    assert response.data["analysis"]["columns_used"] == ["product", "units"]
    assert response.data["result"]["rows"] == [["Widget", 5], ["Gadget", 4]]
    assert "calculated value of 5" in response.data["answer"]
    assert [item["name"] for item in provider.seen_schema] == ["product", "units", "revenue"]


@pytest.mark.django_db
def test_analyze_api_computes_aggregate_and_does_not_accept_unknown_columns(monkeypatch):
    user = User.objects.create_user(username="analyst", password="Strong-pass-209!")
    dataset = create_dataset(user)
    client = APIClient()
    client.force_authenticate(user)

    monkeypatch.setattr("dashboard.ai.service.get_analysis_provider", lambda: PlannedProvider({
        "operation": "aggregate", "value_column": "revenue", "aggregation": "sum",
    }))
    response = client.post(reverse("api_analyze"), {
        "dataset_id": dataset.pk, "question": "What is the total revenue?",
    }, format="json")
    assert response.status_code == 200
    assert response.data["result"]["rows"] == [["revenue", "Sum", 100]]

    monkeypatch.setattr("dashboard.ai.service.get_analysis_provider", lambda: PlannedProvider({
        "operation": "aggregate", "value_column": "not_a_column", "aggregation": "sum",
    }))
    invalid_plan = client.post(reverse("api_analyze"), {
        "dataset_id": dataset.pk, "question": "Add an unknown field",
    }, format="json")
    assert invalid_plan.status_code == 503
    assert "valid value column" in invalid_plan.data["detail"]


@pytest.mark.django_db
def test_analyze_api_validates_authentication_dataset_ownership_and_input(monkeypatch):
    owner = User.objects.create_user(username="owner", password="Strong-pass-209!")
    other = User.objects.create_user(username="other", password="Strong-pass-209!")
    dataset = create_dataset(owner)
    client = APIClient()

    assert client.post(reverse("api_analyze"), {}, format="json").status_code == 401
    client.force_authenticate(other)
    assert client.post(reverse("api_analyze"), {
        "dataset_id": dataset.pk, "question": "Summarize it",
    }, format="json").status_code == 404
    invalid = client.post(reverse("api_analyze"), {
        "dataset_id": dataset.pk, "question": "   ",
    }, format="json")
    assert invalid.status_code == 400
    monkeypatch.undo()


@pytest.mark.django_db
def test_analyze_api_reports_missing_gemini_key_clearly():
    user = User.objects.create_user(username="gemini-api-setup", password="Strong-pass-209!")
    dataset = create_dataset(user)
    client = APIClient()
    client.force_authenticate(user)

    with override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY=""):
        response = client.post(reverse("api_analyze"), {
            "dataset_id": dataset.pk,
            "question": "What is the total revenue?",
        }, format="json")

    assert response.status_code == 503
    assert "GEMINI_API_KEY" in response.data["detail"]
    assert "OpenAI" not in response.data["detail"]


@pytest.mark.django_db
def test_analyst_page_requires_login_and_renders_chat_controls(client):
    url = reverse("analyst")
    assert client.get(url).status_code == 302
    user = User.objects.create_user(username="page-user", password="Strong-pass-209!")
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert b"Analyze dataset" in response.content
    assert b"analyst-question" in response.content
    assert b"Thinking" not in response.content


@pytest.mark.django_db
def test_analyst_page_explains_missing_gemini_setup(client):
    from django.test import override_settings

    user = User.objects.create_user(username="gemini-setup", password="Strong-pass-209!")
    client.force_login(user)
    with override_settings(AI_PROVIDER="gemini", GEMINI_API_KEY=""):
        response = client.get(reverse("analyst"))
    assert response.status_code == 200
    assert b"One setup step left" in response.content
    assert b"aistudio.google.com/api-keys" in response.content


def test_openai_provider_sends_planning_request_and_parses_plan(monkeypatch):
    import dashboard.ai.providers.openai_provider as provider_module

    returned = {"choices": [{"message": {"content": json.dumps({
        "operation": "count_rows", "group_by": None, "value_column": None,
        "aggregation": "count", "order": "desc", "limit": 5,
    })}}]}
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return BytesIO(json.dumps(returned).encode())

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)
    with override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="test-model"):
        plan = OpenAIAnalysisProvider().create_plan("How many rows?", [{"name": "id", "data_type": "int64"}])

    assert plan["operation"] == "count_rows"
    request, timeout = requests[0]
    assert request.full_url == OpenAIAnalysisProvider.endpoint
    assert request.get_header("Authorization") == "Bearer test-key"
    assert json.loads(request.data)["model"] == "test-model"
    assert timeout == 30


def test_openai_provider_reports_missing_api_key():
    with override_settings(OPENAI_API_KEY=""):
        provider = OpenAIAnalysisProvider()
    with pytest.raises(AnalysisProviderError, match="OPENAI_API_KEY"):
        provider.create_plan("Question", [])


def test_openai_provider_explains_exhausted_credits_without_leaking_key(monkeypatch):
    import dashboard.ai.providers.openai_provider as provider_module
    from urllib.error import HTTPError

    def reject_request(request, timeout):
        raise HTTPError(
            request.full_url,
            429,
            "Too Many Requests",
            hdrs=None,
            fp=BytesIO(json.dumps({"error": {"code": "credit_balance_exhausted"}}).encode()),
        )

    monkeypatch.setattr(provider_module, "urlopen", reject_request)
    with override_settings(OPENAI_API_KEY="test-secret", OPENAI_MODEL="test-model"):
        provider = OpenAIAnalysisProvider()
    with pytest.raises(AnalysisProviderError, match="credits or the project spending limit") as error:
        provider.create_plan("Question", [])
    assert "test-secret" not in str(error.value)


def test_gemini_provider_sends_json_planning_request(monkeypatch):
    import dashboard.ai.providers.gemini_provider as provider_module

    returned = {"candidates": [{"content": {"parts": [{"text": json.dumps({
        "operation": "count_rows", "group_by": None, "value_column": None,
        "aggregation": "count", "order": "desc", "limit": 5,
    })}]}}]}
    requests = []

    def fake_urlopen(request, timeout):
        requests.append((request, timeout))
        return BytesIO(json.dumps(returned).encode())

    monkeypatch.setattr(provider_module, "urlopen", fake_urlopen)
    with override_settings(GEMINI_API_KEY="test-key", GEMINI_MODEL="test-model"):
        plan = GeminiAnalysisProvider().create_plan("How many rows?", [{"name": "id", "data_type": "int64"}])

    assert plan["operation"] == "count_rows"
    request, timeout = requests[0]
    assert request.full_url.endswith("/models/test-model:generateContent")
    assert request.get_header("X-goog-api-key") == "test-key"
    payload = json.loads(request.data)
    assert payload["generationConfig"]["responseMimeType"] == "application/json"
    assert "How many rows?" in payload["contents"][0]["parts"][0]["text"]
    assert timeout == 45


def test_gemini_provider_reports_missing_api_key():
    with override_settings(GEMINI_API_KEY=""):
        provider = GeminiAnalysisProvider()
    with pytest.raises(AnalysisProviderError, match="GEMINI_API_KEY"):
        provider.create_plan("Question", [])
