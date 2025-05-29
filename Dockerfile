# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    # wkhtmltopdf and dependencies for PDF generation
    wkhtmltopdf \
    xvfb \
    # Additional dependencies for wkhtmltopdf
    libfontconfig1 \
    libxrender1 \
    libxtst6 \
    libxi6 \
    libxrandr2 \
    libasound2 \
    libatk1.0-0 \
    libgtk-3-0 \
    # Build tools for Python packages
    gcc \
    g++ \
    # File type detection
    libmagic1 \
    # PostgreSQL client libraries
    libpq-dev \
    # Cleanup
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create a wrapper script for wkhtmltopdf to handle headless environment (as root)
RUN echo '#!/bin/bash\nxvfb-run -a --server-args="-screen 0 1024x768x24" wkhtmltopdf "$@"' > /usr/local/bin/wkhtmltopdf-wrapper && \
    chmod +x /usr/local/bin/wkhtmltopdf-wrapper

# Create a non-root user
RUN useradd --create-home --shell /bin/bash app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies (including requests for health check)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir requests

# Create necessary directories
RUN mkdir -p /app/data /app/migrations && \
    chown -R app:app /app

# Copy application code
COPY . .

# Set ownership of the application directory
RUN chown -R app:app /app

# Switch to non-root user
USER app

# Set environment variables for the application
ENV WKHTMLTOPDF_PATH=/usr/bin/wkhtmltopdf
ENV DATA_DIR=/app/data

# Expose the port the app runs on
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/ping')" || exit 1

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"] 