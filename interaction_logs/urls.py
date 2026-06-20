from django.urls import path

from .views import LogInteractionView, SessionLogsView

app_name = "interaction_logs"

urlpatterns = [
    path("", LogInteractionView.as_view(), name="log"),
    path("session/<str:session_id>/", SessionLogsView.as_view(), name="session-logs"),
]
