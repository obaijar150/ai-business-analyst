from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from dashboard.models import Dataset


User = get_user_model()


def make_csv(name="sales.csv", content=b"region,revenue,units\nEast,10,2\nWest,20,3\n"):
    return SimpleUploadedFile(name, content, content_type="text/csv")


@pytest.mark.django_db
def test_csv_upload_stores_file_schema_statistics_and_preview(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    user = User.objects.create_user(username="analyst", password="Strong-pass-209!")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(reverse("api_datasets"), {"file": make_csv(), "name": "Regional sales"}, format="multipart")

    assert response.status_code == 201
    record = Dataset.objects.get(owner=user)
    assert record.name == "Regional sales"
    assert record.file_type == "csv"
    assert record.file.storage.exists(record.file.name)
    assert record.row_count == 2
    assert record.column_count == 3
    assert record.columns[1]["name"] == "revenue"
    assert record.columns[1]["data_type"] == "int64"
    assert record.statistics["numeric"]["revenue"]["mean"] == 15
    assert response.data["metadata"]["preview"][0]["region"] == "East"


@pytest.mark.django_db
def test_excel_upload_and_default_name():
    content = BytesIO()
    pd.DataFrame({"product": ["A", "B"], "quantity": [3, 8]}).to_excel(content, index=False)
    user = User.objects.create_user(username="excel-user", password="Strong-pass-209!")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(reverse("api_datasets"), {
        "file": SimpleUploadedFile("inventory.xlsx", content.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
    }, format="multipart")

    assert response.status_code == 201
    record = Dataset.objects.get(owner=user)
    assert record.name == "inventory.xlsx"
    assert record.row_count == 2
    assert record.statistics["numeric"]["quantity"]["max"] == 8


@pytest.mark.django_db
def test_dataset_list_detail_and_delete_are_scoped_to_owner(tmp_path, settings):
    settings.MEDIA_ROOT = tmp_path
    owner = User.objects.create_user(username="owner", password="Strong-pass-209!")
    other = User.objects.create_user(username="other", password="Strong-pass-209!")
    client = APIClient()
    client.force_authenticate(owner)
    created = client.post(reverse("api_datasets"), {"file": make_csv()}, format="multipart")
    dataset_id = created.data["id"]
    stored = Dataset.objects.get(pk=dataset_id)
    stored_path = stored.file.path

    assert client.get(reverse("api_datasets")).data[0]["id"] == dataset_id
    assert client.get(reverse("api_dataset_detail", args=[dataset_id])).status_code == 200
    client.force_authenticate(other)
    assert client.get(reverse("api_datasets")).data == []
    assert client.get(reverse("api_dataset_detail", args=[dataset_id])).status_code == 404
    assert client.delete(reverse("api_dataset_detail", args=[dataset_id])).status_code == 404

    client.force_authenticate(owner)
    assert client.delete(reverse("api_dataset_detail", args=[dataset_id])).status_code == 204
    assert not Dataset.objects.filter(pk=dataset_id).exists()
    assert not Path(stored_path).exists()


@pytest.mark.django_db
def test_upload_rejects_unsupported_file_and_invalid_csv():
    user = User.objects.create_user(username="analyst", password="Strong-pass-209!")
    client = APIClient()
    client.force_authenticate(user)

    unsupported = client.post(reverse("api_datasets"), {"file": make_csv("notes.txt")}, format="multipart")
    malformed = client.post(reverse("api_datasets"), {"file": make_csv(content=b'"unclosed,header\n')}, format="multipart")

    assert unsupported.status_code == 400
    assert malformed.status_code == 400
    assert Dataset.objects.count() == 0


@pytest.mark.django_db
def test_datasets_page_requires_login_and_renders_for_authenticated_user(client):
    url = reverse("datasets")
    assert client.get(url).status_code == 302
    user = User.objects.create_user(username="page-user", password="Strong-pass-209!")
    client.force_login(user)
    response = client.get(url)
    assert response.status_code == 200
    assert b"Drop your dataset here" in response.content
    assert b"Dataset details" in response.content


@pytest.mark.django_db
def test_dataset_api_requires_authentication():
    client = APIClient()
    response = client.get(reverse("api_datasets"))
    assert response.status_code == 401
