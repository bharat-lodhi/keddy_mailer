#!/bin/bash

echo "🛑 Stopping Gunicorn..."
sudo systemctl stop gunicorn

echo "🛑 Stopping Celery Worker..."
sudo systemctl stop celery

echo "🛑 Stopping Celery Beat..."
sudo systemctl stop celerybeat

echo "🌐 Restarting Nginx..."
sudo systemctl restart nginx

echo "✅ All services stopped."
