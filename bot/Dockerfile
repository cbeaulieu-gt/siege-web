FROM python:3.12-slim

# Inject build metadata at image build time so the /version endpoint can
# surface the full version string (e.g. 1.0.1+42.abc1234).
# Default to "unknown" when building locally without passing --build-arg.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA
ARG BUILD_NUMBER=unknown
ENV BUILD_NUMBER=$BUILD_NUMBER

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8001

CMD ["python", "-m", "app.main"]
