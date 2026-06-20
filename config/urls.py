"""URL configuration for the InteractorGate backend."""
from django.contrib import admin
from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("admin/", admin.site.urls),
    # JWT token refresh (login/logout live under users)
    path("api/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    # App routes
    path("api/users/", include("users.urls")),
    path("api/predictions/", include("predictions.urls")),
    path("api/logs/", include("interaction_logs.urls")),
]
