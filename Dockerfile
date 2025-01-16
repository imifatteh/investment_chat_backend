# Stage 1: Builder stage
FROM python:3.10-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system dependencies including postgres client
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    gcc \
    python3-dev \
    postgresql-client \
    git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Split and install dependencies
RUN pip install --upgrade pip && \
    grep -i "torch\|nvidia\|cuda" requirements.txt > ml-requirements.txt || true && \
    grep -iv "torch\|nvidia\|cuda" requirements.txt > other-requirements.txt || true

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
    -r ml-requirements.txt \
    -f https://download.pytorch.org/whl/cpu \
    --index-url https://pypi.org/simple

RUN pip wheel --no-cache-dir --no-deps --wheel-dir /wheels \
    -r other-requirements.txt \
    --index-url https://pypi.org/simple

# Stage 2: Final runtime stage
FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install runtime dependencies including postgres client
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create and activate virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy wheels and install
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/*

# Copy project files
COPY . .

EXPOSE $PORT

# Run migrations and start the application
CMD ["bash", "-c", "python manage.py migrate --noinput && exec gunicorn investment_chat_project.wsgi:application --bind 0.0.0.0:$PORT"]
