# Audio Pipeline SRE Documentation

## Overview

This document provides comprehensive Site Reliability Engineering (SRE) guidance for the AI Teddy Bear audio pipeline. The audio pipeline is a critical component that handles text-to-speech (TTS), speech-to-text (STT), audio validation, safety checks, and streaming for child-safe AI interactions.

## Architecture Overview

### Core Components

```
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│   AudioService  │────│  Validation      │────│   Safety Service   │
│   (Coordinator) │    │  Service         │    │   (Child Safety)   │
└─────────────────┘    └──────────────────┘    └────────────────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────┐    ┌──────────────────┐    ┌────────────────────┐
│  OpenAI TTS     │    │  Streaming       │    │   Production       │
│  Provider       │    │  Service         │    │   TTS Cache        │
└─────────────────┘    └──────────────────┘    └────────────────────┘
```

### Service Dependencies

- **AudioService**: Main coordinator service
- **OpenAI TTS Provider**: Production TTS implementation
- **Audio Validation Service**: Audio format and quality validation
- **Audio Safety Service**: Child safety and content filtering
- **Audio Streaming Service**: Stream processing and buffering
- **Production TTS Cache**: Redis-based caching layer

## Service Level Objectives (SLOs)

### Availability SLOs
- **Audio Pipeline Availability**: 99.9% uptime
- **TTS Service Availability**: 99.95% uptime
- **Cache Service Availability**: 99.8% uptime

### Performance SLOs
- **TTS Response Time**: P95 < 5 seconds, P99 < 10 seconds
- **Audio Validation**: P95 < 100ms
- **Safety Check**: P95 < 200ms
- **Cache Hit Rate**: > 80% for repeated requests

### Quality SLOs
- **Safety Violation Detection**: > 99% accuracy
- **Audio Quality Score**: > 0.7 average
- **Content Filter Effectiveness**: > 99.5% for inappropriate content

## Monitoring and Alerting

### Key Metrics

#### TTS Metrics
```
tts_requests_total{provider, voice_id, language, status, cached}
tts_processing_duration_seconds{provider, voice_id, model}
tts_cache_hit_ratio
tts_cost_total_usd{provider, model}
tts_characters_processed_total{provider, language, content_type}
```

#### Audio Safety Metrics
```
audio_safety_checks_total{check_type, result, child_age_group}
audio_safety_violations_total{violation_type, severity, action_taken}
audio_validation_checks_total{format, result, error_type}
```

#### Child Engagement Metrics
```
child_audio_sessions_total{age_group, session_type, duration_bucket}
child_audio_engagement_duration_seconds{age_group, content_type}
```

#### Error Metrics
```
audio_errors_total{error_type, component, severity}
tts_provider_health_score{provider, region}
```

### Alert Rules

#### Critical Alerts (PagerDuty)
```yaml
# TTS Service Down
- alert: TTSServiceDown
  expr: tts_provider_health_score < 0.5
  for: 2m
  severity: critical
  
# High Error Rate
- alert: AudioHighErrorRate
  expr: rate(audio_errors_total[5m]) > 0.1
  for: 3m
  severity: critical

# Safety System Failure
- alert: SafetySystemFailure
  expr: rate(audio_safety_violations_total{action_taken="blocked"}[10m]) == 0
  for: 5m
  severity: critical
```

#### Warning Alerts (Slack)
```yaml
# High TTS Latency
- alert: HighTTSLatency
  expr: histogram_quantile(0.95, tts_processing_duration_seconds) > 5
  for: 5m
  severity: warning

# Low Cache Hit Rate
- alert: LowCacheHitRate
  expr: tts_cache_hit_ratio < 0.6
  for: 10m
  severity: warning

# High TTS Costs
- alert: HighTTSCosts
  expr: increase(tts_cost_total_usd[1h]) > 50
  for: 0m
  severity: warning
```

### Health Check Endpoints

#### Primary Health Checks
- `GET /health/audio` - Overall audio pipeline health
- `GET /health/audio/tts` - TTS provider specific health
- `GET /health/audio/metrics` - Metrics collection health

#### Response Format
```json
{
  "status": "healthy|degraded|unhealthy",
  "timestamp": "2025-01-15T10:30:00Z",
  "audio_processing": {
    "total_requests": 1000,
    "success_rate": 0.995
  },
  "tts_service": {
    "provider_health": {
      "status": "healthy",
      "provider": "openai",
      "response_time_ms": 1250
    }
  },
  "production_cache": {
    "hit_rate": 0.85,
    "size_mb": 512,
    "health": "healthy"
  }
}
```

## Runbooks

### Incident Response

#### 1. TTS Service Degradation

**Symptoms**: High latency, timeouts, error rate increase

**Investigation Steps**:
1. Check TTS provider health: `curl /health/audio/tts`
2. Verify OpenAI API status: https://status.openai.com
3. Check error logs: `kubectl logs -f deployment/audio-service`
4. Review metrics: `/metrics/audio`

**Resolution**:
```bash
# Check TTS service status
kubectl get pods -l app=audio-service

# Restart unhealthy pods
kubectl delete pod -l app=audio-service --field-selector=status.phase!=Running

# Verify API key configuration
kubectl get secret openai-api-key -o yaml

# Check circuit breaker status
curl /health/audio | jq '.tts_service.circuit_breaker'
```

#### 2. Safety System Failure

**Symptoms**: Inappropriate content getting through, zero blocked violations

**Critical Actions**:
1. **IMMEDIATE**: Enable emergency content blocking
2. Check safety service logs for errors
3. Verify safety rule configuration
4. Test safety filters manually

**Commands**:
```bash
# Emergency safety mode (blocks all content)
kubectl patch configmap audio-config --patch '{"data":{"EMERGENCY_SAFETY_MODE":"true"}}'

# Check safety service
kubectl logs -f deployment/audio-service | grep -i safety

# Test safety endpoint
curl -X POST /api/internal/safety/test -d '{"text":"test inappropriate content"}'
```

#### 3. Cache Service Issues

**Symptoms**: High TTS costs, increased latency, low hit rates

**Investigation**:
```bash
# Check Redis status
kubectl get pods -l app=redis

# Review cache metrics
curl /health/audio/metrics | grep cache

# Check cache configuration
kubectl get configmap redis-config -o yaml
```

**Resolution**:
```bash
# Restart Redis
kubectl rollout restart deployment/redis

# Clear corrupted cache if needed (CAUTION)
kubectl exec redis-0 -- redis-cli FLUSHDB

# Verify cache connectivity
kubectl exec deployment/audio-service -- redis-cli -h redis ping
```

### Performance Tuning

#### TTS Optimization

**Cache Configuration**:
```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: tts-cache-config
data:
  TTS_CACHE_ENABLED: "true"
  TTS_CACHE_TTL: "3600"
  TTS_CACHE_MAX_SIZE_MB: "2048"
  TTS_CACHE_COMPRESSION: "2"
  TTS_CACHE_STRATEGY: "cost_aware"
```

**OpenAI TTS Settings**:
```yaml
OPENAI_TTS_MODEL: "tts-1"  # or "tts-1-hd" for higher quality
TTS_PROVIDER: "openai"
TTS_REQUEST_TIMEOUT: "30"
TTS_MAX_RETRIES: "3"
```

#### Scaling Guidelines

**Horizontal Scaling**:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: audio-service
spec:
  replicas: 3  # Minimum for HA
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
```

**Resource Limits**:
```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "250m"
  limits:
    memory: "1Gi"
    cpu: "500m"
```

### Capacity Planning

#### TTS Usage Estimation
- **Average Text Length**: 50-200 characters
- **Average Cost per Request**: $0.001-$0.003
- **Peak Load**: 100 requests/minute
- **Daily Cost Estimate**: $50-150

#### Storage Requirements
- **Cache Storage**: 2-5GB for optimal hit rates
- **Log Storage**: 1GB/day for debugging
- **Metrics Storage**: 100MB/day for monitoring

## Security Considerations

### COPPA Compliance
- All child interactions logged with age verification
- Content filtering mandatory for users under 13
- Parental consent tracking for data retention

### API Security
- OpenAI API keys rotated monthly
- Rate limiting: 1000 requests/hour per user
- Request/response logging for audit trails

### Data Privacy
- Audio data processed in memory only
- No persistent storage of voice recordings
- TTS cache keys anonymized (hashed)

## Configuration Management

### Environment Variables
```bash
# Core Configuration
OPENAI_API_KEY=sk-...
TTS_PROVIDER=openai
OPENAI_TTS_MODEL=tts-1

# Cache Configuration
TTS_CACHE_ENABLED=true
TTS_CACHE_TTL=3600
REDIS_URL=redis://redis:6379

# Safety Configuration
TTS_CHILD_SAFETY=true
AUDIO_SAFETY_STRICT_MODE=true
```

### Kubernetes Secrets
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: audio-service-secrets
type: Opaque
stringData:
  OPENAI_API_KEY: "sk-..."
  REDIS_PASSWORD: "..."
```

## Deployment Procedures

### Rolling Deployment
```bash
# Deploy new version
kubectl set image deployment/audio-service audio-service=teddy-bear/audio:v1.2.3

# Monitor deployment
kubectl rollout status deployment/audio-service

# Verify health
curl /health/audio

# Rollback if needed
kubectl rollout undo deployment/audio-service
```

### Canary Deployment
```yaml
apiVersion: argoproj.io/v1alpha1
kind: Rollout
metadata:
  name: audio-service
spec:
  strategy:
    canary:
      steps:
      - setWeight: 10
      - pause: {duration: "5m"}
      - setWeight: 50
      - pause: {duration: "10m"}
      - setWeight: 100
```

## Disaster Recovery

### Backup Procedures
- Configuration backup: Daily automated
- Cache warm-up scripts: Ready for cold start
- Metrics/logs: 30-day retention

### Recovery Time Objectives (RTO)
- **Service Restart**: < 2 minutes
- **Cache Rebuild**: < 10 minutes
- **Full DR**: < 30 minutes

### Recovery Procedures
```bash
# Quick recovery
kubectl apply -f audio-service-manifest.yaml
kubectl rollout restart deployment/audio-service

# Cache warm-up
kubectl exec deployment/audio-service -- python scripts/cache_warmup.py

# Verify recovery
./scripts/health_check.sh
```

## Contact Information

### On-Call Rotation
- **Primary**: SRE Team Slack: #sre-oncall  
- **Secondary**: Engineering Team: #engineering-alerts
- **Escalation**: CTO/VP Engineering

### Service Ownership
- **Service Owner**: Audio Engineering Team
- **SRE Contact**: @sre-audio-team
- **Product Owner**: @product-audio

### External Dependencies
- **OpenAI Status**: https://status.openai.com
- **Redis Cloud**: https://status.redis.com
- **AWS Status**: https://status.aws.amazon.com

---

## Changelog

- **2025-01-15**: Initial SRE documentation
- **Version**: 1.0.0
- **Last Updated**: 2025-01-15
- **Next Review**: 2025-04-15