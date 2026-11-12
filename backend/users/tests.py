import pytest
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_registration():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {
            "username": "testuser",
            "email": "test@example.com",
            "password": "StrongPass@123"
        },
        format="json"
    )

    assert response.status_code == 201

    user = User.objects.get(username="testuser")

    assert user.email == "test@example.com"
    assert user.check_password("StrongPass@123")

@pytest.mark.django_db
def test_duplicate_email_registration():
    User.objects.create_user(
        username="existing",
        email="test@example.com",
        password="StrongPass@123"
    )

    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {
            "username": "anotheruser",
            "email": "test@example.com",
            "password": "AnotherPass@123"
        },
        format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_invalid_password_registration():
    client = APIClient()

    response = client.post(
        "/api/v1/auth/register/",
        {
            "username": "weakuser",
            "email": "weak@example.com",
            "password": "123"
        },
        format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_unauthenticated_user_cannot_access_profile():
    client = APIClient()

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 401

@pytest.mark.django_db
def test_email_login_success():
    User.objects.create_user(
        username="loginuser",
        email="login@example.com",
        password="StrongPass@123"
    )

    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {
            "email": "login@example.com",
            "password": "StrongPass@123"
        },
        format="json"
    )

    assert response.status_code == 200
    assert "access" in response.data
    assert "refresh" in response.data


@pytest.mark.django_db
def test_email_login_wrong_password():
    User.objects.create_user(
        username="loginuser",
        email="login@example.com",
        password="StrongPass@123"
    )

    client = APIClient()

    response = client.post(
        "/api/v1/auth/login/",
        {
            "email": "login@example.com",
            "password": "WrongPassword123!"
        },
        format="json"
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_token_refresh_success():
    user = User.objects.create_user(
        username="refreshuser",
        email="refresh@example.com",
        password="StrongPass@123"
    )

    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)

    client = APIClient()

    response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": str(refresh)},
        format="json"
    )

    assert response.status_code == 200
    assert "access" in response.data


@pytest.mark.django_db
def test_refresh_token_rejected_after_logout():
    user = User.objects.create_user(
        username="logoutuser",
        email="logout@example.com",
        password="StrongPass@123"
    )

    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {access}"
    )

    logout_response = client.post(
        "/api/v1/auth/logout/",
        {"refresh": str(refresh)},
        format="json"
    )

    assert logout_response.status_code == 205

    refresh_response = client.post(
        "/api/v1/auth/token/refresh/",
        {"refresh": str(refresh)},
        format="json"
    )

    assert refresh_response.status_code == 401


@pytest.mark.django_db
def test_authenticated_user_can_access_profile():
    user = User.objects.create_user(
        username="profileuser",
        email="profile@example.com",
        password="StrongPass@123"
    )

    from rest_framework_simplejwt.tokens import RefreshToken

    refresh = RefreshToken.for_user(user)
    access = str(refresh.access_token)

    client = APIClient()
    client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {access}"
    )

    response = client.get("/api/v1/auth/me/")

    assert response.status_code == 200
    assert response.data["email"] == "profile@example.com"
    assert response.data["username"] == "profileuser"
