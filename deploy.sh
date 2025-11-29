#!/bin/bash
set -e

echo "🚀 Starting Keddy Mailer Deployment..."

# Load environment
if [ -f .env.production ]; then
    export $(cat .env.production | grep -v '^#' | xargs)
else
    echo "❌ .env.production not found!"
    exit 1
fi

git pull origin main

echo "🐳 Building containers..."
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml build --no-cache
docker-compose -f docker-compose.prod.yml up -d

sleep 10

echo "🗃️ Running migrations..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py migrate --noinput

echo "📦 Collecting static files..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py collectstatic --noinput

# ✅ CUSTOM ADMIN CREATION FOR YOUR USER MODEL
echo "👑 Creating admin user for CustomUser model..."
docker-compose -f docker-compose.prod.yml exec -T web python manage.py shell -c "
from keddy_mailer.models import CustomUser
from django.contrib.auth.hashers import make_password

if not CustomUser.objects.filter(role='admin').exists():
    admin = CustomUser(
        name='Keddy Admin',
        email='admin@keddytech.in', 
        number='9999999999',
        password=make_password('admin123'),
        dob='2000-01-01',
        address='Keddy Tech',
        company='Keddy Tech',
        role='admin',
        email_credit_limit=10000,
        is_active=True
    )
    admin.save()
    print('✅ Custom Admin user created')
else:
    print('✅ Admin user exists')
"

echo "🔍 Service status:"
docker-compose -f docker-compose.prod.yml ps

echo "🎉 Deployment completed!"
echo "🌐 https://keddytech.in"
echo "🔑 Admin: admin@keddytech.in / admin123"