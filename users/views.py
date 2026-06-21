from django.contrib.auth import get_user_model
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import UserProfileSerializer, UserRegisterSerializer

User = get_user_model()


class LoginView(TokenObtainPairView):
    """POST /api/users/login/ — issue a JWT pair, rate-limited against brute force."""

    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "login"


class RegisterView(generics.CreateAPIView):
    """POST /api/users/register/ — public user registration (rate-limited)."""

    queryset = User.objects.all()
    permission_classes = (AllowAny,)
    serializer_class = UserRegisterSerializer
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "register"


class LogoutView(APIView):
    """POST /api/users/logout/ — blacklist the supplied refresh token."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return Response(
                {"detail": "El token 'refresh' es obligatorio."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            RefreshToken(refresh_token).blacklist()
        except TokenError:
            return Response(
                {"detail": "Token inválido o expirado."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(status=status.HTTP_205_RESET_CONTENT)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """GET/PUT/PATCH /api/users/me/ — the authenticated user's own profile."""

    permission_classes = (IsAuthenticated,)
    serializer_class = UserProfileSerializer

    def get_object(self):
        return self.request.user
