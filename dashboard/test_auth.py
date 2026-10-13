import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient


User = get_user_model()


@pytest.mark.django_db
def test_registration_creates_and_logs_in_user(client):
    response = client.post(reverse("register"), {
        "username": "new-analyst",
        "password1": "A-strong-password-294!",
        "password2": "A-strong-password-294!",
    })

    assert response.status_code == 302
    assert response.url == reverse("dashboard")
    assert User.objects.filter(username="new-analyst").exists()
    assert int(client.session["_auth_user_id"]) == User.objects.get(username="new-analyst").id


@pytest.mark.django_db
def test_registration_shows_password_errors(client):
    response = client.post(reverse("register"), {
        "username": "analyst",
        "password1": "short",
        "password2": "different",
    })

    assert response.status_code == 200
    assert b"password" in response.content.lower()
    assert not User.objects.filter(username="analyst").exists()


@pytest.mark.django_db
def test_login_and_logout_use_session_authentication(client):
    User.objects.create_user(username="analyst", password="A-strong-password-294!")

    login_response = client.post(reverse("login"), {
        "username": "analyst",
        "password": "A-strong-password-294!",
    })
    assert login_response.status_code == 302
    assert login_response.url == reverse("dashboard")

    logout_response = client.post(reverse("logout"))
    assert logout_response.status_code == 302
    assert logout_response.url == reverse("login")
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_invalid_login_shows_authentication_error(client):
    User.objects.create_user(username="analyst", password="A-strong-password-294!")

    response = client.post(reverse("login"), {
        "username": "analyst",
        "password": "incorrect-password",
    })

    assert response.status_code == 200
    assert b"correct username and password" in response.content.lower()


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get(reverse("dashboard"))
    assert response.status_code == 302
    assert response.url.startswith(f"{reverse('login')}?")


@pytest.mark.django_db
def test_api_registration_jwt_current_user_and_logout():
    client = APIClient()
    registered = client.post(reverse("api_auth_register"), {
        "username": "api-analyst",
        "password": "A-strong-password-294!",
    }, format="json")
    assert registered.status_code == 201
    assert registered.data["username"] == "api-analyst"

    anonymous = client.get(reverse("api_current_user"))
    assert anonymous.status_code == 401

    login = client.post(reverse("api_auth_login"), {
        "username": "api-analyst",
        "password": "A-strong-password-294!",
    }, format="json")
    assert login.status_code == 200
    access_token = login.data["access"]
    refresh_token = login.data["refresh"]

    client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")
    current_user = client.get(reverse("api_current_user"))
    assert current_user.status_code == 200
    assert current_user.data["username"] == "api-analyst"

    logout = client.post(reverse("api_auth_logout"), {"refresh": refresh_token}, format="json")
    assert logout.status_code == 205
    refresh_after_logout = client.post(reverse("api_token_refresh"), {"refresh": refresh_token}, format="json")
    assert refresh_after_logout.status_code == 401


@pytest.mark.django_db
def test_api_registration_reports_validation_errors():
    client = APIClient()
    response = client.post(reverse("api_auth_register"), {
        "username": "analyst",
        "password": "short",
    }, format="json")
    assert response.status_code == 400
    assert "password" in response.data
