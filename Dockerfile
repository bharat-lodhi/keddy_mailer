# Use official Python runtime as base image
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
# ENV DJANGO_SETTINGS_MODULE=keddy_mailer.settings
ENV DJANGO_SETTINGS_MODULE=keddy_mailer.settings_production 

# Set work directory
WORKDIR /app

# Install system dependencies required for PostgreSQL and other packages
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    postgresql-dev \
    python3-dev \
    musl-dev \
    libffi-dev \
    openssl \
    libssl-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for better Docker caching)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create necessary directories
RUN mkdir -p \
    logs \
    staticfiles \
    media

# Collect static files
RUN python manage.py collectstatic --noinput

# Expose port
EXPOSE 8000

# Create non-root user for security
RUN useradd -m -r keddyuser && chown -R keddyuser:keddyuser /app
USER keddyuser

# Start Gunicorn server
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "4", "--threads", "4", "keddy_mailer.wsgi:application"]