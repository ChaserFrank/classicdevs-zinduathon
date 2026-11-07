# One image for web, worker and beat; the command differs per service.
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_RETRIES=10

WORKDIR /app

# REQUIREMENTS=dev for docker-compose (tests, ruff); prod for deployments.
ARG REQUIREMENTS=prod
COPY requirements/ requirements/
RUN pip install -r requirements/${REQUIREMENTS}.txt

COPY . .

# Collect static assets (admin, Swagger/ReDoc sidecar) at build time. A dummy key is enough here.
RUN DJANGO_SECRET_KEY=build-only DJANGO_SETTINGS_MODULE=config.settings.prod \
    python manage.py collectstatic --noinput

RUN useradd --create-home --uid 1000 app && chown -R app /app
USER app

ENV DJANGO_SETTINGS_MODULE=config.settings.prod \
    PORT=8080

EXPOSE 8080
# See start.sh: ROLE=all (default; web + worker + beat), web, worker or beat.
CMD ["./start.sh"]
