#!/bin/bash
set -e

# Wait for database if needed
# python /app/manage.py wait_for_db

# Run migrations
python manage.py migrate --noinput

# Start the application
exec "$@"