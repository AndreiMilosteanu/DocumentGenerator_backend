# Performance Optimization Guide

This guide provides comprehensive performance optimizations for the Document Generator Backend, especially for deployment on droplets or cloud servers.

## 🚀 Quick Performance Improvements (Immediate Impact)

### 1. Use the Optimized OpenAI Client
The application now includes an optimized OpenAI client that provides:
- **50% faster polling** (250ms vs 500ms intervals)
- **Connection pooling** and reuse
- **Active run tracking** to prevent duplicate requests
- **Reduced timeouts** (60s vs 120s) for faster failure detection
- **Optimized message retrieval** (limit to recent messages)

**Already implemented** - no action needed!

### 2. Configure Multiple Uvicorn Workers
```bash
# Instead of:
uvicorn main:app --host 0.0.0.0 --port 8000

# Use:
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 3. Set Performance Environment Variables
Add to your `.env` file:
```bash
# Performance optimizations
PYTHONUNBUFFERED=1
DEBUG=False
GPT_MODEL=gpt-4-turbo  # Faster than regular gpt-4
```

## 📊 Performance Testing

Run the performance optimization script:
```bash
python scripts/optimize_performance.py
```

This will:
- Test OpenAI API response times
- Check your environment configuration
- Provide specific recommendations
- Create an optimized `.env` template

## 🔧 Detailed Optimizations

### OpenAI API Optimizations

#### 1. Configure Topic-Specific Assistants
Instead of using one assistant for all topics, configure specialized assistants:

```bash
# In your .env file
ASSISTANT_ID=your_default_assistant_id
DEKLARATIONSANALYSE_ASSISTANT_ID=asst_specialized_for_deklarationsanalyse
BODENUNTERSUCHUNG_ASSISTANT_ID=asst_specialized_for_bodenuntersuchung
BAUGRUNDGUTACHTEN_ASSISTANT_ID=asst_specialized_for_baugrundgutachten
PLATTENDRUCKVERSUCH_ASSISTANT_ID=asst_specialized_for_plattendruckversuch
```

**Benefits:**
- Faster responses (specialized context)
- Better accuracy
- Reduced token usage

#### 2. Monitor Cache Performance
Check cache effectiveness:
```bash
curl http://localhost:8000/conversation/{document_id}/performance-stats
```

### Database Optimizations

#### 1. Use PostgreSQL (Recommended for Production)
```bash
# Instead of SQLite
DATABASE_URL=sqlite:///./data/app.db

# Use PostgreSQL
DATABASE_URL=postgresql://user:password@localhost/document_generator
```

#### 2. Add Database Indexes
```sql
-- Add indexes for frequently queried fields
CREATE INDEX idx_documents_topic ON documents(topic);
CREATE INDEX idx_chat_messages_document_section ON chat_messages(document_id, section, subsection);
CREATE INDEX idx_file_uploads_document_status ON file_uploads(document_id, status);
CREATE INDEX idx_approved_subsections_document ON approved_subsections(document_id);
```

### Server Configuration

#### 1. Optimized Uvicorn Configuration
```bash
# Production command
uvicorn main:app \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 2 \
  --worker-class uvicorn.workers.UvicornWorker \
  --access-log \
  --log-level info
```

#### 2. Systemd Service with Optimizations
```ini
[Unit]
Description=Document Generator Backend (Optimized)
After=network.target

[Service]
Type=simple
User=your-app-user
WorkingDirectory=/path/to/DocumentGenerator_backend
ExecStart=/path/to/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2

# Performance Environment Variables
Environment=PYTHONUNBUFFERED=1
Environment=DEBUG=False
Environment=UVICORN_WORKERS=2

# PDF Environment Variables
Environment=QT_QPA_PLATFORM=offscreen
Environment=DISPLAY=:99

# Your application variables
Environment=OPENAI_API_KEY=your_key
Environment=DATABASE_URL=your_db_url

Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

### Droplet-Specific Optimizations

#### 1. Memory Optimization
```bash
# Check current memory usage
free -h

# Add swap if needed (for 1GB droplets)
sudo fallocate -l 1G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

#### 2. Nginx Reverse Proxy (Recommended)
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # Gzip compression
    gzip on;
    gzip_types text/plain application/json application/javascript text/css;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Timeout optimizations
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

## 📈 Performance Monitoring

### 1. Application Metrics
Monitor these endpoints:
- `/conversation/{document_id}/performance-stats` - OpenAI optimization stats
- `/health` - Application health (if implemented)

### 2. System Monitoring
```bash
# Monitor CPU and memory
htop

# Monitor disk usage
df -h

# Monitor network
iftop

# Monitor application logs
journalctl -u your-app -f
```

### 3. OpenAI API Monitoring
Track these metrics:
- Average response time per request
- Cache hit rate
- Number of active runs
- Token usage

## 🎯 Expected Performance Improvements

With these optimizations, you should see:

| Metric | Before | After | Improvement |
|--------|--------|-------|-------------|
| Simple reply | 15-30s | 8-15s | ~50% faster |
| File upload processing | 30-60s | 15-30s | ~50% faster |
| Thread creation | 2-5s | 1-2s | ~60% faster |
| Message sending | 1-3s | 0.5-1s | ~50% faster |

## 🚨 Troubleshooting Performance Issues

### Slow OpenAI Responses
1. Check your internet connection on the droplet
2. Verify OpenAI API key is valid
3. Monitor OpenAI API status
4. Check cache hit rates

### High Memory Usage
1. Reduce number of Uvicorn workers
2. Add swap space
3. Monitor for memory leaks
4. Consider upgrading droplet size

### Database Slowness
1. Add appropriate indexes
2. Switch from SQLite to PostgreSQL
3. Monitor query performance
4. Consider connection pooling

### PDF Generation Issues
1. Ensure wkhtmltopdf is properly installed
2. Check environment variables
3. Monitor disk space
4. Verify font availability

## 🔄 Continuous Optimization

### Regular Tasks
1. **Weekly**: Run performance tests
2. **Monthly**: Review cache statistics
3. **Quarterly**: Update dependencies
4. **As needed**: Scale resources based on usage

### Monitoring Alerts
Set up alerts for:
- Response time > 30 seconds
- Memory usage > 80%
- Disk usage > 85%
- Error rate > 5%

## 📝 Quick Start Checklist

- [ ] Run `python scripts/optimize_performance.py`
- [ ] Configure multiple Uvicorn workers
- [ ] Set performance environment variables
- [ ] Configure topic-specific assistants (if available)
- [ ] Set up Nginx reverse proxy
- [ ] Add database indexes
- [ ] Configure monitoring
- [ ] Test performance improvements

## 🆘 Need Help?

If you're still experiencing performance issues:

1. Run the diagnostic script: `python scripts/optimize_performance.py`
2. Check the performance stats endpoint
3. Review application logs
4. Consider upgrading your droplet resources

The optimizations in this guide should significantly improve your application's performance, especially for OpenAI API interactions which are typically the bottleneck. 