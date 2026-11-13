"""Azure AI Speech: short-lived tokens for the desktop app's text-to-speech.

The subscription key never leaves the server. The client exchanges its JWT for
an Azure token (valid 10 minutes) and calls the Azure TTS REST API directly, so
the composed text does not pass through or get stored by this backend.
"""
import urllib.error
import urllib.request

from django.conf import settings
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

# Azure tokens last 10 minutes; tell the client to renew a minute earlier.
TOKEN_TTL_SECONDS = 540
ISSUE_TIMEOUT_SECONDS = 10


def issue_azure_token(key: str, region: str) -> str:
    """POST to the regional STS endpoint and return the bearer token."""
    req = urllib.request.Request(
        f"https://{region}.api.cognitive.microsoft.com/sts/v1.0/issueToken",
        data=b"",
        method="POST",
        headers={"Ocp-Apim-Subscription-Key": key, "Content-Length": "0"},
    )
    with urllib.request.urlopen(req, timeout=ISSUE_TIMEOUT_SECONDS) as res:
        return res.read().decode("ascii").strip()


class SpeechTokenView(APIView):
    """GET /api/speech/token/ — Azure Speech token, region and voice."""

    permission_classes = (IsAuthenticated,)
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "speech"

    def get(self, request):
        key = settings.AZURE_SPEECH_KEY
        region = settings.AZURE_SPEECH_REGION
        if not key or not region:
            return Response(
                {"detail": "La síntesis de voz no está configurada."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        try:
            token = issue_azure_token(key, region)
        except (urllib.error.URLError, TimeoutError, OSError):
            return Response(
                {"detail": "No se pudo contactar el servicio de voz."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        if not token:
            return Response(
                {"detail": "El servicio de voz no devolvió un token."},
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                "token": token,
                "region": region,
                "voice": settings.AZURE_SPEECH_VOICE,
                "expires_in": TOKEN_TTL_SECONDS,
            },
            headers={"Cache-Control": "no-store"},
        )
