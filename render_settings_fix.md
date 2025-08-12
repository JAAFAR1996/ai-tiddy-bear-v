# 🔧 Render Settings Fix Guide

## Critical Changes Needed:

### 1. Health Check Path
```
CHANGE FROM: /healthz
CHANGE TO:   /health
```

### 2. Docker Command  
```
CHANGE FROM: uvicorn src.main:app --host 0.0.0.0 --port $PORT --workers 1 --log-level info

CHANGE TO:   uvicorn src.main:app --host 0.0.0.0 --port $PORT --workers 1 --timeout-keep-alive 30 --log-level info
```

### 3. Pre-Deploy Command
```
CHANGE FROM: pip install --upgrade pip && pip install --cache-dir=/tmp/pip-cache -r requirements.txt && python -c "import fastapi, uvicorn, sqlalchemy, redis, openai; print('✅ All core dependencies loaded successfully')"

CHANGE TO:   pip install --upgrade pip && pip install -r requirements.txt
```

### 4. Environment Variables (Missing)
Add these in Environment Variables section:
```
ELEVENLABS_API_KEY=your-elevenlabs-key-here
ALLOWED_HOSTS=["ai-tiddy-bear-v-xuqy.onrender.com"]
```

### 5. Optional: Region Change
```
CURRENT: Frankfurt (EU Central)
BETTER:  Virginia (US East) - faster for Middle East users
```

## Priority Order:
1. ✅ Fix Health Check Path (/health)
2. ✅ Add missing environment variables  
3. ✅ Simplify Pre-Deploy Command
4. ⚡ Update Docker Command
5. 🌍 Consider region change

After making these changes, redeploy the service.