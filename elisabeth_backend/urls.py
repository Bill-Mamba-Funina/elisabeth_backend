from django.contrib import admin
from django.shortcuts import redirect
from django.urls import path, include

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)


def frontend(request):
    return redirect("http://localhost:3000/")


urlpatterns = [
    # Redirige Django vers Next.js
    path("", frontend, name="frontend"),

    # Administration Django
    path("admin/", admin.site.urls),

    # Authentification JWT
    path(
        "api/auth/token/",
        TokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),

    path(
        "api/auth/refresh/",
        TokenRefreshView.as_view(),
        name="token_refresh",
    ),

    # API Elisabeth
    path(
        "api/",
        include("application_elisabeth.urls"),
    ),
]