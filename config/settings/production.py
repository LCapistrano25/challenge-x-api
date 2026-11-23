from . import base

SECRET_KEY = base.SECRET_KEY
DEBUG = False
ALLOWED_HOSTS = base.env.list("DJANGO_ALLOWED_HOSTS")

INSTALLED_APPS = base.INSTALLED_APPS
MIDDLEWARE = base.MIDDLEWARE
ROOT_URLCONF = base.ROOT_URLCONF
TEMPLATES = base.TEMPLATES
WSGI_APPLICATION = base.WSGI_APPLICATION
DATABASES = base.DATABASES
AUTH_PASSWORD_VALIDATORS = base.AUTH_PASSWORD_VALIDATORS
LANGUAGE_CODE = base.LANGUAGE_CODE
TIME_ZONE = base.TIME_ZONE
USE_I18N = base.USE_I18N
USE_TZ = base.USE_TZ
STATIC_URL = base.STATIC_URL
# collectstatic grava aqui; o Caddy serve /static/ desta pasta (docker-compose.prod).
STATIC_ROOT = base.BASE_DIR / "staticfiles"
# Origem do frontend (https://...), exigida pelo CSRF da sessão em HTTPS. Na
# homologação o front usa o proxy do Vite: http://localhost:5173.
CSRF_TRUSTED_ORIGINS = base.env.list("DJANGO_CSRF_TRUSTED_ORIGINS", default=[])
# SMTP via EMAIL_URL (ex.: smtp+tls://usuario:senha@smtp.servidor.com:587).
# shortcut: sem EMAIL_URL o e-mail só vai para o log; configurar antes da produção.
vars().update(base.env.email_url("EMAIL_URL", default="consolemail://"))
STORAGES = base.STORAGES
DELIVERY_STORAGE_ROOT = base.DELIVERY_STORAGE_ROOT
DELIVERY_MAX_FILE_MB = base.DELIVERY_MAX_FILE_MB
DEFAULT_AUTO_FIELD = base.DEFAULT_AUTO_FIELD
AUTH_USER_MODEL = base.AUTH_USER_MODEL
DEFAULT_FROM_EMAIL = base.DEFAULT_FROM_EMAIL
SESSION_COOKIE_AGE = base.SESSION_COOKIE_AGE
SESSION_SAVE_EVERY_REQUEST = base.SESSION_SAVE_EVERY_REQUEST
REST_FRAMEWORK = base.REST_FRAMEWORK
MICROSOFT_TENANT_ID = base.MICROSOFT_TENANT_ID
MICROSOFT_CLIENT_ID = base.MICROSOFT_CLIENT_ID
MICROSOFT_CLIENT_SECRET = base.MICROSOFT_CLIENT_SECRET
MICROSOFT_REDIRECT_URI = base.MICROSOFT_REDIRECT_URI

SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
# Atrás de proxy que termina o TLS o Django só vê HTTP; sem isto o redirecionamento
# acima não termina nunca. shortcut: confia no cabeçalho de qualquer origem, então o
# proxy deve sobrescrevê-lo; sem proxy, remover esta linha.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
# shortcut: 1 hora, para errar barato; subir para 31536000 (1 ano) quando o site
# inteiro estiver confirmado em HTTPS.
SECURE_HSTS_SECONDS = 3600
# Preload e subdomínios no HSTS são difíceis de desfazer; ficam fora de propósito.
SILENCED_SYSTEM_CHECKS = ["security.W005", "security.W021"]
