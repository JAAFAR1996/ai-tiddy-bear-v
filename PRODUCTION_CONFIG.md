# Production Configuration Guide

## Required Environment Variables for Render

### CORS & Security
```bash
# Production domains for CORS
CORS_ALLOWED_ORIGINS=["https://ai-tiddy-bear-v-xuqy.onrender.com","https://aiteddybear.com","https://www.aiteddybear.com","https://api.aiteddybear.com"]

# Allowed host headers
ALLOWED_HOSTS=["ai-tiddy-bear-v-xuqy.onrender.com","aiteddybear.com","www.aiteddybear.com","api.aiteddybear.com"]

# Primary host
HOST=ai-tiddy-bear-v-xuqy.onrender.com
```

### Database & Redis
```bash
DATABASE_URL=postgresql+asyncpg://[your-database-url]
REDIS_URL=redis://[your-redis-url]
```

### Authentication & Security
```bash
JWT_SECRET_KEY=[generate-secure-key]
ESP32_SHARED_SECRET=[your-esp32-secret]
```

### AI Services
```bash
OPENAI_API_KEY=[your-openai-key]
```

### Payment (When Ready)
```bash
STRIPE_SECRET_KEY=sk_live_[your-stripe-key]
STRIPE_PUBLISHABLE_KEY=pk_live_[your-stripe-key]
```

### Performance & Monitoring
```bash
WEB_CONCURRENCY=1
GUNICORN_WORKERS=1
LOG_LEVEL=INFO
DEBUG_IMPORTS=false
```

### Optional Settings
```bash
METRICS_USERNAME=[your-metrics-user]
METRICS_PASSWORD=[your-metrics-pass]
MIGRATIONS_DATABASE_URL=postgresql+psycopg2://[same-as-database-url]
```

## Domain Configuration

### Current Production Domains:
- **Primary**: `https://ai-tiddy-bear-v-xuqy.onrender.com`
- **Future Main**: `https://aiteddybear.com`
- **Future WWW**: `https://www.aiteddybear.com`
- **Future API**: `https://api.aiteddybear.com`

### ESP32 Connection:
- Endpoint: `POST https://ai-tiddy-bear-v-xuqy.onrender.com/api/v1/pair/claim`
- Content-Type: `application/json`

## Security Notes:
1. Never commit `.env` files with real credentials
2. Use Render's environment variable interface for sensitive data
3. Rotate JWT_SECRET_KEY periodically
4. Keep ESP32_SHARED_SECRET synchronized with devices