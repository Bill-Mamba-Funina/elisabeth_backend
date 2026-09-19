from pathlib import Path
import os
from datetime import timedelta

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret")

DEBUG = os.environ.get("DJANGO_DEBUG", "1") == "1"

ALLOWED_HOSTS = ["*"]

# ============================================================

# APPLICATIONS

# ============================================================

INSTALLED_APPS = [
"django.contrib.admin",
"django.contrib.auth",
"django.contrib.contenttypes",
"django.contrib.sessions",
"django.contrib.messages",
"django.contrib.staticfiles",


"corsheaders",
"rest_framework",

"application_elisabeth",


]

# ============================================================

# MIDDLEWARE

# ============================================================

MIDDLEWARE = [
"corsheaders.middleware.CorsMiddleware",


"django.middleware.security.SecurityMiddleware",

"django.contrib.sessions.middleware.SessionMiddleware",

"django.middleware.common.CommonMiddleware",

"django.middleware.csrf.CsrfViewMiddleware",

"django.contrib.auth.middleware.AuthenticationMiddleware",

"django.contrib.messages.middleware.MessageMiddleware",

"django.middleware.clickjacking.XFrameOptionsMiddleware",


]

# ============================================================

# URLS

# ============================================================

ROOT_URLCONF = "elisabeth_backend.urls"

# ============================================================

# TEMPLATES

# ============================================================

TEMPLATES = [
{
"BACKEND": "django.template.backends.django.DjangoTemplates",
"DIRS": [],
"APP_DIRS": True,
"OPTIONS": {
"context_processors": [
"django.template.context_processors.debug",
"django.template.context_processors.request",
"django.contrib.auth.context_processors.auth",
"django.contrib.messages.context_processors.messages",
],
},
},
]

# ============================================================

# WSGI / ASGI

# ============================================================

WSGI_APPLICATION = "elisabeth_backend.wsgi.application"
ASGI_APPLICATION = "elisabeth_backend.asgi.application"

# ============================================================

# BASE DE DONNÉES POSTGRESQL

# ============================================================

DATABASES = {
"default": {
"ENGINE": "django.db.backends.postgresql",


    "NAME": os.environ.get(
        "PGDATABASE",
        "elisabeth_bdd",
    ),

    "USER": os.environ.get(
        "PGUSER",
        "postgres",
    ),

    "PASSWORD": os.environ.get(
        "PGPASSWORD",
        "billmamba2025",
    ),

    "HOST": os.environ.get(
        "PGHOST",
        "127.0.0.1",
    ),

    "PORT": os.environ.get(
        "PGPORT",
        "5432",
    ),
}


}

# ============================================================

# INTERNATIONALISATION

# ============================================================

LANGUAGE_CODE = "fr-fr"

TIME_ZONE = os.environ.get(
"TZ",
"Africa/Kinshasa",
)

USE_I18N = True

USE_TZ = True

# ============================================================

# FICHIERS STATIQUES

# ============================================================

STATIC_URL = "/static/"

# ============================================================

# DJANGO REST FRAMEWORK

# ============================================================

REST_FRAMEWORK = {
"DEFAULT_AUTHENTICATION_CLASSES": (
"rest_framework_simplejwt.authentication.JWTAuthentication",
),
}

# ============================================================

# CORS

# ============================================================

CORS_ALLOW_ALL_ORIGINS = True

# ============================================================

# JWT

# ============================================================

SIMPLE_JWT = {
"ACCESS_TOKEN_LIFETIME": timedelta(hours=8),


"REFRESH_TOKEN_LIFETIME": timedelta(days=30),


}
