import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model


def test_health_endpoint_returns_ok(client):
    response = client.get(reverse("health"))
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.django_db
def test_dashboard_renders(client):
    user = get_user_model().objects.create_user(username="analyst", password="ComplexPass!234")
    client.force_login(user)
    response = client.get(reverse("dashboard"))
    assert response.status_code == 200
    assert b"Good morning" in response.content
    assert b"Log out" in response.content
