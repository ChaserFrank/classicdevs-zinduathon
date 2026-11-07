#!/bin/sh
# Container entrypoint. ROLE decides what this container runs:
#   all    (default) migrate, then gunicorn + a Celery worker with embedded beat, in one container.
#          For platforms that run one HTTP service per deployment (RumptyCloud).
#   web    migrate, then gunicorn only (docker-compose / VM, with separate worker and beat).
#   worker Celery worker only.
#   beat   Celery beat only.
set -eu

ROLE="${ROLE:-all}"
PORT="${PORT:-8080}"
WEB_CONCURRENCY="${WEB_CONCURRENCY:-2}"        # 2 gunicorn workers fit a 512 MB instance
CELERY_CONCURRENCY="${CELERY_CONCURRENCY:-2}"

gunicorn_cmd() {
  exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT}" \
    --workers "${WEB_CONCURRENCY}" \
    --timeout 60 \
    --access-logfile - \
    --forwarded-allow-ips "*"
}

case "$ROLE" in
  all)
    python manage.py migrate --noinput
    # -B embeds beat in the worker: correct for exactly one instance (the free tier's maximum).
    celery -A config worker -B --loglevel=INFO --concurrency "${CELERY_CONCURRENCY}" \
      --schedule /tmp/celerybeat-schedule &
    CELERY_PID=$!
    gunicorn_cmd &
    GUNICORN_PID=$!
    # sh is PID 1 and doesn't forward signals: pass SIGTERM/SIGINT on to both children.
    STOPPING=0
    trap 'STOPPING=1; kill -TERM "$GUNICORN_PID" "$CELERY_PID" 2>/dev/null || true' INT TERM
    # Supervise: if either process dies, stop the other and exit non-zero so the platform
    # restarts the whole container (a web server without its worker would leave analyses queued).
    while kill -0 "$GUNICORN_PID" 2>/dev/null && kill -0 "$CELERY_PID" 2>/dev/null; do
      sleep 2
    done
    kill -TERM "$GUNICORN_PID" "$CELERY_PID" 2>/dev/null || true
    wait
    [ "$STOPPING" = 1 ] && exit 0
    echo "A process exited unexpectedly; stopping the container." >&2
    exit 1
    ;;
  web)
    python manage.py migrate --noinput
    gunicorn_cmd
    ;;
  worker)
    exec celery -A config worker --loglevel=INFO --concurrency "${CELERY_CONCURRENCY}"
    ;;
  beat)
    exec celery -A config beat --loglevel=INFO --schedule /tmp/celerybeat-schedule
    ;;
  *)
    echo "Unknown ROLE '$ROLE' (use all, web, worker or beat)" >&2
    exit 64
    ;;
esac
