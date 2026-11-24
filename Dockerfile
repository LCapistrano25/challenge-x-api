FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.10.8 /uv /bin/uv

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/venv \
    PATH="/venv/bin:$PATH" \
    DJANGO_SETTINGS_MODULE=config.settings.production

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY . .

RUN useradd --create-home app \
    && mkdir -p /app/staticfiles /data/deliveries \
    && chown app /app/staticfiles /data/deliveries
USER app

EXPOSE 8000
# Um processo com threads: cabe em 1 GB e mantém o limite de login (cache por
# processo, ver DEFAULT_THROTTLE_RATES) valendo para o servidor inteiro.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput && exec gunicorn config.wsgi -b 0.0.0.0:8000 --workers 1 --threads 4 --timeout 60"]
