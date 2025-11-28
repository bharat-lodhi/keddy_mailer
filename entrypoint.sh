#!/bin/sh
# entrypoint.sh - run migrations & collectstatic then start gunicorn

set -e

# wait for DB to be ready (simple loop)
if [ -n "$POSTGRES_HOST" ]; then
  echo "Waiting for Postgres..."
  until nc -z -v -w30 $POSTGRES_HOST $POSTGRES_PORT
  do
    echo "Waiting for database connection at $POSTGRES_HOST:$POSTGRES_PORT..."
    sleep 2
  done
fi

# run migrations
echo "Running migrations..."
python manage.py migrate --noinput

# collect static
echo "Collecting static files..."
python manage.py collectstatic --noinput

# create superuser if env provided (optional)
if [ "$DJANGO_SUPERUSER_USERNAME" ] && [ "$DJANGO_SUPERUSER_EMAIL" ] && [ "$DJANGO_SUPERUSER_PASSWORD" ]; then
  python manage.py createsuperuser --noinput || true
fi

# start gunicorn
echo "Starting Gunicorn..."
exec gunicorn keddy_mailer.wsgi:application --bind 0.0.0.0:8000 --workers 4
