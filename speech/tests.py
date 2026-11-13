"""Tests for the Azure Speech token endpoint (Azure is mocked)."""
import urllib.error
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()
CONFIGURED = {
    "AZURE_SPEECH_KEY": "secret-key",
    "AZURE_SPEECH_REGION": "eastus",
    "AZURE_SPEECH_VOICE": "es-PE-CamilaNeural",
}


class SpeechTokenTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="p01", password="x")
        self.url = reverse("speech:token")
        self.client.force_authenticate(self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    @override_settings(AZURE_SPEECH_KEY="", AZURE_SPEECH_REGION="")
    def test_not_configured_returns_503(self):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    @override_settings(**CONFIGURED)
    @mock.patch("speech.views.issue_azure_token", return_value="azure-jwt")
    def test_returns_token_without_exposing_key(self, issue):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["token"], "azure-jwt")
        self.assertEqual(res.data["region"], "eastus")
        self.assertEqual(res.data["voice"], "es-PE-CamilaNeural")
        self.assertEqual(res.data["expires_in"], 540)
        self.assertEqual(res["Cache-Control"], "no-store")
        self.assertNotIn("secret-key", res.content.decode())
        issue.assert_called_once_with("secret-key", "eastus")

    @override_settings(**CONFIGURED)
    @mock.patch(
        "speech.views.issue_azure_token",
        side_effect=urllib.error.URLError("down"),
    )
    def test_azure_failure_returns_502(self, _issue):
        res = self.client.get(self.url)
        self.assertEqual(res.status_code, status.HTTP_502_BAD_GATEWAY)
