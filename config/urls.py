from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/predictions/', include('predictions.urls')),
    path('api/logs/', include('interaction_logs.urls')),
]
