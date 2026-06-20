from django.urls import path

from .views import PredictionHistoryView, PredictionView

app_name = "predictions"

urlpatterns = [
    path("", PredictionView.as_view(), name="predict"),
    path("history/", PredictionHistoryView.as_view(), name="history"),
]
