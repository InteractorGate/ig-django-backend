"""Public, unauthenticated service endpoints (root index + health check)."""
from django.http import JsonResponse


def root(request):
    """GET / — friendly API index so the base URL isn't a bare 404."""
    return JsonResponse(
        {
            "service": "InteractorGate API",
            "status": "ok",
            "endpoints": {
                "register": "/api/users/register/",
                "login": "/api/users/login/",
                "profile": "/api/users/me/",
                "predictions": "/api/predictions/",
                "logs": "/api/logs/",
                "admin": "/admin/",
                "health": "/healthz/",
            },
        }
    )


def healthz(request):
    """GET /healthz/ — lightweight liveness probe for monitoring."""
    return JsonResponse({"status": "ok"})
