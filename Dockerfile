FROM python:3.10-slim

WORKDIR /app

# Install system dependencies including fonts and wkhtmltopdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    wkhtmltopdf \
    xvfb \
    fonts-liberation \
    fonts-dejavu-core \
    fontconfig \
    libjpeg-dev \
    libpng-dev \
    libxrender1 \
    libxext6 \
    libfontconfig1 \
    libx11-6 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables for headless operation
ENV QT_QPA_PLATFORM=offscreen
ENV DISPLAY=:99

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