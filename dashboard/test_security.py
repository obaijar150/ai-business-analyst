import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient

from dashboard.models import Dataset, Report


User = get_user_model()


def make_dataset(user):
    return Dataset.objects.create(
        owner=user,
        name="private.csv",
        file=SimpleUploadedFile("private.csv", b"x,y\n1,2\n", content_type="text/csv"),
        file_type="csv",
        row_count=1,
        column_count=2,
        columns=[],
        statistics={},
        metadata={},
    )


@pytest.mark.django_db
def test_dataset_detail_requires_owner():
    owner = User.objects.create_user(username="owner", password="Strong-pass-209!")
    other = User.objects.create_user(username="other", password="Strong-pass-209!")
    dataset = make_dataset(owner)

    client = APIClient()
    client.force_authenticate(other)
    response = client.get(reverse("api_dataset_detail", args=[dataset.pk]))
    assert response.status_code == 404


@pytest.mark.django_db
def test_analyze_requires_dataset_owner():
    owner = User.objects.create_user(username="owner2", password="Strong-pass-209!")
    other = User.objects.create_user(username="other2", password="Strong-pass-209!")
    dataset = make_dataset(owner)

    client = APIClient()
    client.force_authenticate(other)
    response = client.post(reverse("api_analyze"), {"dataset_id": dataset.pk, "question": "total"}, format="json")
    assert response.status_code == 404


@pytest.mark.django_db
def test_reports_are_isolated_by_owner():
    owner = User.objects.create_user(username="owner3", password="Strong-pass-209!")
    other = User.objects.create_user(username="other3", password="Strong-pass-209!")
    dataset = make_dataset(owner)
    report = Report.objects.create(
        owner=owner,
        dataset=dataset,
        title="Private report",
        executive_summary="summary",
    )

    client = APIClient()
    client.force_authenticate(other)
    detail = client.get(reverse("api_report_detail", args=[report.pk]))
    listing = client.get(reverse("api_reports"))
    assert detail.status_code == 404
    assert listing.status_code == 200
    assert not any(item["id"] == report.pk for item in listing.data)