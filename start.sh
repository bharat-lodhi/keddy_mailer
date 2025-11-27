#!/bin/bash

echo "🔄 Activating virtual environment..."
source /home/ubuntu/keddy-mailer/venv/bin/activate

echo "📂 Navigating to project directory..."
cd /home/ubuntu/keddy-mailer

echo "📦 Collecting static files..."
python manage.py collectstatic --noinput

echo "🧠 Running migrations..."
python manage.py migrate

echo "🚀 Starting Gunicorn..."
sudo systemctl restart gunicorn

echo "⚙️  Starting Celery Worker..."
sudo systemctl restart celery

echo "⏰ Starting Celery Beat..."
sudo systemctl restart celerybeat

echo "🌐 Restarting Nginx..."
sudo systemctl restart nginx

echo "✅ Keddy Mailer started successfully!"
