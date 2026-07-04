"""Tests for the users app: registration, JWT auth, profile, logout, throttling."""
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework.throttling import ScopedRateThrottle

User = get_user_model()


class RegistrationTests(APITestCase):
    def setUp(self):
        self.url = reverse("users:register")
        self.payload = {
            "username": "eduardo",
            "email": "eduardo@example.com",
            "password": "SecurePass123",
            "password2": "SecurePass123",
        }

    def test_register_success(self):
        res = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(username="eduardo")
        self.assertEqual(user.email, "eduardo@example.com")
        # Password must be stored hashed, never in plain text.
        self.assertNotEqual(user.password, "SecurePass123")
        self.assertTrue(user.check_password("SecurePass123"))
        # The response must not leak the password.
        self.assertNotIn("password", res.data)

    def test_register_password_mismatch(self):
        payload = {**self.payload, "password2": "Different123"}
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(username="eduardo").exists())

    def test_register_weak_password(self):
        payload = {**self.payload, "password": "123", "password2": "123"}
        res = self.client.post(self.url, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_register_duplicate_username(self):
        User.objects.create_user(username="eduardo", password="x")
        res = self.client.post(self.url, self.payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class AuthFlowTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="eduardo", email="e@e.com", password="SecurePass123"
        )
        self.login_url = reverse("users:login")
        self.me_url = reverse("users:me")
        self.logout_url = reverse("users:logout")
        self.refresh_url = reverse("token_refresh")

    def _login(self):
        return self.client.post(
            self.login_url,
            {"username": "eduardo", "password": "SecurePass123"},
            format="json",
        )

    def test_login_returns_token_pair(self):
        res = self._login()
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

    def test_login_wrong_password(self):
        res = self.client.post(
            self.login_url,
            {"username": "eduardo", "password": "wrong"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_requires_authentication(self):
        res = self.client.get(self.me_url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_me_returns_profile_when_authenticated(self):
        self.client.force_authenticate(self.user)
        res = self.client.get(self.me_url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["username"], "eduardo")
        self.assertEqual(res.data["email"], "e@e.com")

    def test_me_update_patches_editable_fields_only(self):
        self.client.force_authenticate(self.user)
        res = self.client.patch(
            self.me_url,
            {"first_name": "Ed", "username": "hacker"},
            format="json",
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, "Ed")
        # username is read-only: it must not change.
        self.assertEqual(self.user.username, "eduardo")

    def test_logout_blacklists_refresh_token(self):
        self.client.force_authenticate(self.user)
        refresh = str(self._login().data["refresh"])
        res = self.client.post(self.logout_url, {"refresh": refresh}, format="json")
        self.assertEqual(res.status_code, status.HTTP_205_RESET_CONTENT)
        # The blacklisted refresh token can no longer be used to refresh.
        self.client.force_authenticate(user=None)
        again = self.client.post(self.refresh_url, {"refresh": refresh}, format="json")
        self.assertEqual(again.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_logout_requires_refresh_token(self):
        self.client.force_authenticate(self.user)
        res = self.client.post(self.logout_url, {}, format="json")
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class LoginThrottleTests(APITestCase):
    """The login endpoint is scoped-throttled against brute force."""

    def setUp(self):
        cache.clear()  # throttle history lives in the cache
        self.login_url = reverse("users:login")

    def tearDown(self):
        cache.clear()

    def test_login_is_throttled_after_limit(self):
        payload = {"username": "nobody", "password": "wrong"}
        # Force a low login rate for this test (DRF binds THROTTLE_RATES as a
        # class attribute, so patch that dict rather than override_settings).
        with patch.dict(ScopedRateThrottle.THROTTLE_RATES, {"login": "3/min"}):
            # First 3 attempts are allowed (401 wrong creds), the 4th is throttled.
            for _ in range(3):
                res = self.client.post(self.login_url, payload, format="json")
                self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
            throttled = self.client.post(self.login_url, payload, format="json")
            self.assertEqual(
                throttled.status_code, status.HTTP_429_TOO_MANY_REQUESTS
            )
