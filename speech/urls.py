from django.urls import path

from .views import SpeechTokenView

app_name = "speech"

urlpatterns = [
    path("token/", SpeechTokenView.as_view(), name="token"),
]
