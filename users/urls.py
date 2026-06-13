from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView

from .views import LogoutView, RegisterView, UserProfileView

app_name = "users"

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", TokenObtainPairView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("me/", UserProfileView.as_view(), name="me"),
]
