# DocumentGenerator Backend - Docker Setup

This guide explains how to run the DocumentGenerator backend using Docker and Docker Compose.

## Prerequisites

- Docker and Docker Compose installed on your system
- OpenAI API key
- OpenAI Assistant ID(s)

## Quick Start

1. **Clone the repository** (if not already done):
   ```bash
   git clone <repository-url>
   cd DocumentGenerator_backend
   ```

2. **Set up environment variables**:
   Create a `.env` file in the root directory with the following variables:
   ```env
   # OpenAI Configuration (REQUIRED)
   OPENAI_API_KEY=your_openai_api_key_here
   ASSISTANT_ID=your_default_assistant_id_here
   GPT_MODEL=gpt-4o

   # Topic-specific OpenAI Assistants (optional)
   DEKLARATIONSANALYSE_ASSISTANT_ID=
   BODENUNTERSUCHUNG_ASSISTANT_ID=
   BAUGRUNDGUTACHTEN_ASSISTANT_ID=
   PLATTENDRUCKVERSUCH_ASSISTANT_ID=

   # JWT Configuration (REQUIRED)
   JWT_SECRET_KEY=your-super-secret-jwt-key-change-this-in-production

   # Database Configuration (optional - defaults provided)
   DATABASE_URL=postgresql://postgres:postgres@db:5432/documentgenerator
   ```

3. **Start the application**:
   ```bash
   docker-compose up -d
   ```

4. **Run database migrations**:
   ```bash
   docker-compose exec api aerich upgrade
   ```

5. **Access the application**:
   - API: http://localhost:8000
   - API Documentation: http://localhost:8000/docs
   - Health Check: http://localhost:8000/ping

## Docker Services

### API Service (`api`)
- **Port**: 8000
- **Image**: Built from local Dockerfile
- **Dependencies**: PostgreSQL database
- **Volumes**: `app_data` for persistent file storage
- **Health Check**: Checks `/ping` endpoint every 30 seconds

### Database Service (`db`)
- **Port**: 5432
- **Image**: postgres:15-alpine
- **Database**: documentgenerator
- **Credentials**: postgres/postgres
- **Volume**: `postgres_data` for persistent data storage

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `OPENAI_API_KEY` | Your OpenAI API key | `sk-...` |
| `ASSISTANT_ID` | Default OpenAI Assistant ID | `asst_...` |
| `JWT_SECRET_KEY` | Secret key for JWT tokens | `your-secret-key` |

### Optional Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GPT_MODEL` | OpenAI model to use | `gpt-4o` |
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://postgres:postgres@db:5432/documentgenerator` |
| `JWT_ALGORITHM` | JWT algorithm | `HS256` |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | Token expiration time | `43200` (30 days) |
| `WKHTMLTOPDF_PATH` | Path to wkhtmltopdf binary | `/usr/bin/wkhtmltopdf` |
| `DATA_DIR` | Data directory path | `/app/data` |

## Docker Commands

### Build and Start
```bash
# Build and start all services
docker-compose up -d

# Build only (without starting)
docker-compose build

# Start with logs visible
docker-compose up
```

### Database Operations
```bash
# Run database migrations
docker-compose exec api aerich upgrade

# Create new migration
docker-compose exec api aerich migrate

# Access database directly
docker-compose exec db psql -U postgres -d documentgenerator
```

### Logs and Debugging
```bash
# View logs for all services
docker-compose logs

# View logs for specific service
docker-compose logs api
docker-compose logs db

# Follow logs in real-time
docker-compose logs -f api
```

### Maintenance
```bash
# Stop all services
docker-compose down

# Stop and remove volumes (WARNING: This deletes all data)
docker-compose down -v

# Restart specific service
docker-compose restart api

# Update and restart
docker-compose pull
docker-compose up -d
```

## File Structure

```
DocumentGenerator_backend/
├── Dockerfile              # Main application container
├── docker-compose.yml      # Multi-service orchestration
├── .dockerignore           # Files to exclude from build
├── requirements.txt        # Python dependencies
├── main.py                 # FastAPI application entry point
├── config.py              # Application configuration
├── models.py              # Database models
├── routers/               # API route handlers
├── utils/                 # Utility functions
├── templates/             # Document templates
├── migrations/            # Database migrations
└── data/                  # Persistent data (mounted as volume)
```

## Troubleshooting

### Common Issues

1. **Port already in use**:
   ```bash
   # Check what's using port 8000
   lsof -i :8000
   # Or change the port in docker-compose.yml
   ```

2. **Database connection issues**:
   ```bash
   # Check database health
   docker-compose exec db pg_isready -U postgres
   
   # View database logs
   docker-compose logs db
   ```

3. **OpenAI API issues**:
   - Verify your API key is correct
   - Check your OpenAI account has sufficient credits
   - Ensure Assistant IDs are valid

4. **PDF generation issues**:
   - The container includes wkhtmltopdf with xvfb for headless operation
   - Check logs for wkhtmltopdf-related errors

### Health Checks

Both services include health checks:
- **Database**: `pg_isready` command
- **API**: HTTP request to `/ping` endpoint

Check health status:
```bash
docker-compose ps
```

### Performance Tuning

For production deployments:

1. **Resource Limits**: Add resource limits to docker-compose.yml
2. **Environment**: Use production-grade PostgreSQL settings
3. **Secrets**: Use Docker secrets or external secret management
4. **Monitoring**: Add monitoring and logging solutions
5. **Backup**: Implement database backup strategies

## Security Considerations

1. **Change default passwords** in production
2. **Use strong JWT secret keys**
3. **Limit network exposure** (remove port mappings if using reverse proxy)
4. **Regular updates** of base images and dependencies
5. **Secure file upload** validation and storage

## Development

For development with live code reloading:

```bash
# Mount source code as volume
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up
```

Create `docker-compose.dev.yml`:
```yaml
version: '3.8'
services:
  api:
    volumes:
      - .:/app
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
``` 