FROM python:3.10-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    wkhtmltopdf \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create a non-root user
RUN useradd -m appuser
USER appuser

# Apply database migrations
RUN python migrations.py upgrade || echo "Migrations will be run at startup"

# Expose the port
EXPOSE 8000

# Set up entry point
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 