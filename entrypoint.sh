#!/bin/sh
# entrypoint.sh - run migrations & collectstatic then start gunicorn

set -e

# ---- Variables ----
POSTGRES_HOST="${POSTGRES_HOST:-db}"
POSTGRES_PORT="${POSTGRES_PORT:-5432}"

# ---- Check if 'nc' (netcat) is installed ----
if ! command -v nc >/dev/null 2>&1; then
    echo "[INFO] netcat (nc) not found, installing..."
    apt-get update && apt-get install -y netcat && rm -rf /var/lib/apt/lists/*
fi

# ---- Wait for DB ----
if [ -n "$POSTGRES_HOST" ]; then
    echo "[INFO] Waiting for Postgres at $POSTGRES_HOST:$POSTGRES_PORT..."
    until nc -z -v -w30 $POSTGRES_HOST $POSTGRES_PORT >/dev/null 2>&1
    do
        echo "[INFO] Still waiting for database connection at $POSTGRES_HOST:$POSTGRES_PORT..."
        sleep 2
    done
    echo "[INFO] Database is up!"
fi

# ---- Run migrations ----
echo "[INFO] Running Django migrations..."
python manage.py migrate --noinput

# ---- Collect static files ----
echo "[INFO] Collecting static files..."
python manage.py collectstatic --noinput

# ---- Create superuser if env variables provided ----
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "[INFO] Creating superuser..."
    python manage.py createsuperuser --noinput || echo "[INFO] Superuser already exists or creation skipped."
fi

# ---- Start Gunicorn ----
echo "[INFO] Starting Gunicorn..."
exec gunicorn keddy_mailer.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 4 \
    --access-logfile '-' \
    --error-logfile '-'
