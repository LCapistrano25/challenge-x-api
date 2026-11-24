from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(
    DJANGO_DEBUG=(bool, False),
)

environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("DJANGO_SECRET_KEY")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "apps.core.apps.CoreConfig",
    "apps.accounts.apps.AccountsConfig",
    "apps.editions.apps.EditionsConfig",
    "apps.teams.apps.TeamsConfig",
    "apps.projects.apps.ProjectsConfig",
    "apps.evaluations.apps.EvaluationsConfig",
    "apps.results.apps.ResultsConfig",
    "apps.notifications",
    "apps.public",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT"),
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Araguaina"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"

# Arquivos das entregas (RF31): armazenamento privado, sem URL. O download passa pela
# API, que checa quem pode ver o projeto. Para trocar de backend (ex.: nuvem), mude
# só o alias "deliveries".
DELIVERY_STORAGE_ROOT = env(
    "DELIVERY_STORAGE_ROOT", default=str(BASE_DIR / "private_media")
)
# Teto de tamanho de um arquivo de entrega; vale mesmo que o campo da etapa peça mais.
DELIVERY_MAX_FILE_MB = env.int("DELIVERY_MAX_FILE_MB", default=50)

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    "deliveries": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
        "OPTIONS": {"location": DELIVERY_STORAGE_ROOT},
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "accounts.User"

DEFAULT_FROM_EMAIL = "noreply@desafiox.local"

# Login de aluno e professor com a conta Microsoft (RF18, RF36), app web no Entra ID.
MICROSOFT_TENANT_ID = env("MICROSOFT_TENANT_ID", default="")
MICROSOFT_CLIENT_ID = env("MICROSOFT_CLIENT_ID", default="")
MICROSOFT_CLIENT_SECRET = env("MICROSOFT_CLIENT_SECRET", default="")
MICROSOFT_REDIRECT_URI = env("MICROSOFT_REDIRECT_URI", default="")
# Swagger do contrato em /api/docs/, aberto a quem tiver o link (homologação).
ENABLE_API_DOCS = env.bool("ENABLE_API_DOCS", default=False)

# Sessão com expiração por inatividade
SESSION_COOKIE_AGE = 1800
SESSION_SAVE_EVERY_REQUEST = True

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "apps.core.authentication.SessionAuthentication",
    ],
    # Esquecer permission_classes exige login em vez de deixar a rota aberta.
    # Cada view declara o papel (IsAdmin, IsStudent...) ou AllowAny se pública.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "EXCEPTION_HANDLER": "config.exception.custom_exception_handler",
    "DEFAULT_PAGINATION_CLASS": "config.pagination.DefaultPagination",
    # Tentativas de login por e-mail (EmailRateThrottle).
    # shortcut: o cache padrão é por processo, então o limite vale por processo;
    # com mais de um processo em produção, apontar CACHES para um cache compartilhado.
    "DEFAULT_THROTTLE_RATES": {"login": "5/min"},
}
