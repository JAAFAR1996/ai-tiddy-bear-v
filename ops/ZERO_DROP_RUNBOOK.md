# Zero-Drop WebSocket Operations Runbook

## Overview
This runbook covers zero-drop WebSocket operations for AI Teddy Bear production deployments.

## Quick Reference

### Emergency Commands
```bash
# Check drain status
curl -H "Authorization: Bearer $ADMIN_TOKEN" https://api.aiteddybear.com/admin/drain/status

# Start emergency drain
curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
  -d '{"reason":"emergency","max_session_age_seconds":30}' \
  https://api.aiteddybear.com/admin/drain/start

# Check WebSocket metrics
curl https://api.aiteddybear.com/api/v1/esp32/metrics
```

### Key Metrics to Monitor
- `ws_active`: Active WebSocket connections
- `dropped_messages`: Messages lost during operations (should be 0)
- `ws_resumes`: Successful session resumes
- `resume_failures`: Failed resume attempts
- `rtt_p95_ms`: 95th percentile RTT (should be ≤150ms)

## Standard Operations

### 1. Rolling Deployment (A→B)

#### Pre-deployment Checks
```bash
# Verify current metrics
curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics'

# Check active sessions
ACTIVE_SESSIONS=$(curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.ws_active')
echo "Active sessions: $ACTIVE_SESSIONS"
```

#### Deployment Steps
1. **Deploy new instance (B)**
   ```bash
   # Deploy new version to instance B
   docker-compose -f deployment/docker-compose.production.yml up -d app_replica
   
   # Wait for health check
   until curl -f http://app_replica:8000/health; do sleep 5; done
   ```

2. **Start drain on instance A**
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"reason":"rolling_deployment","max_session_age_seconds":60}' \
     https://api.aiteddybear.com/admin/drain/start
   ```

3. **Monitor drain progress**
   ```bash
   # Watch active sessions decrease
   watch 'curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq ".ws_metrics.ws_active"'
   ```

4. **Complete drain and switch traffic**
   ```bash
   # Wait for sessions to complete or timeout
   # Then update load balancer to route to instance B
   
   # Complete drain
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     https://api.aiteddybear.com/admin/drain/complete
   ```

5. **Verify zero drops**
   ```bash
   # Check for any dropped messages
   DROPPED=$(curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.dropped_messages')
   if [ "$DROPPED" -gt 0 ]; then
     echo "❌ DEPLOYMENT FAILED: $DROPPED messages dropped"
     exit 1
   fi
   echo "✅ Zero-drop deployment successful"
   ```

### 2. Nginx Reload (Zero Downtime)

#### Steps
1. **Test new configuration**
   ```bash
   nginx -t -c /path/to/new/nginx.conf
   ```

2. **Reload with zero downtime**
   ```bash
   # Nginx reload preserves existing connections
   nginx -s reload
   ```

3. **Verify WebSocket connections maintained**
   ```bash
   # Check that active sessions remain stable
   curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.ws_active'
   ```

### 3. Instance Crash Recovery

#### Immediate Response
1. **Check resume store health**
   ```bash
   # Verify Redis is accessible
   redis-cli -u $REDIS_URL ping
   ```

2. **Monitor reconnection metrics**
   ```bash
   # Watch for reconnections and resumes
   watch 'curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq "{reconnects: .ws_metrics.ws_reconnects, resumes: .ws_metrics.ws_resumes, failures: .ws_metrics.resume_failures}"'
   ```

3. **Verify resume success rate**
   ```bash
   # Resume success rate should be >95%
   RESUMES=$(curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.ws_resumes')
   FAILURES=$(curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.resume_failures')
   SUCCESS_RATE=$(echo "scale=2; $RESUMES / ($RESUMES + $FAILURES) * 100" | bc)
   echo "Resume success rate: $SUCCESS_RATE%"
   ```

### 4. Redis Restart

#### Pre-restart
1. **Enable Redis persistence**
   ```bash
   # Ensure RDB snapshots are enabled
   redis-cli CONFIG SET save "900 1 300 10 60 10000"
   ```

2. **Force snapshot**
   ```bash
   redis-cli BGSAVE
   ```

#### During restart
1. **Monitor application behavior**
   ```bash
   # App should handle Redis unavailability gracefully
   curl -s https://api.aiteddybear.com/health
   ```

2. **Check resume store recovery**
   ```bash
   # After Redis restart, verify resume functionality
   curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.resume_store_metrics'
   ```

### 5. Scale Down (2→1 Instance)

#### Steps
1. **Start drain on instance to be removed**
   ```bash
   curl -X POST -H "Authorization: Bearer $ADMIN_TOKEN" \
     -d '{"reason":"scale_down","max_session_age_seconds":120}' \
     https://instance-2.aiteddybear.com/admin/drain/start
   ```

2. **Wait for session migration**
   ```bash
   # Sessions should migrate to remaining instance
   # Monitor both instances
   watch 'echo "Instance 1:"; curl -s https://instance-1.aiteddybear.com/api/v1/esp32/metrics | jq ".ws_metrics.ws_active"; echo "Instance 2:"; curl -s https://instance-2.aiteddybear.com/api/v1/esp32/metrics | jq ".ws_metrics.ws_active"'
   ```

3. **Clean up sticky routing**
   ```bash
   # Remove stale affinity cookies for the removed instance
   # This is handled automatically by TTL, but can be forced
   redis-cli --scan --pattern "sticky:affinity:*" | xargs redis-cli del
   ```

4. **Remove instance**
   ```bash
   docker-compose -f deployment/docker-compose.production.yml stop app_replica
   docker-compose -f deployment/docker-compose.production.yml rm app_replica
   ```

## Troubleshooting

### High Resume Failure Rate

#### Symptoms
- `resume_failures` metric increasing
- Clients reporting connection issues

#### Investigation
```bash
# Check Redis connectivity
redis-cli -u $REDIS_URL ping

# Check resume store metrics
curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.resume_store_metrics'

# Check application logs
docker logs ai-teddy-app-prod | grep -i resume
```

#### Resolution
1. **Verify Redis health**
2. **Check network connectivity**
3. **Restart application if needed**

### Dropped Messages Alert

#### Immediate Actions
```bash
# Check current dropped message count
DROPPED=$(curl -s https://api.aiteddybear.com/api/v1/esp32/metrics | jq '.ws_metrics.dropped_messages')
echo "Dropped messages: $DROPPED"

# If > 0, investigate immediately
if [ "$DROPPED" -gt 0 ]; then
  # Check recent deployments
  # Check system resources
  # Check Redis memory usage
  redis-cli info memory
fi
```

### Sticky Routing Issues

#### Symptoms
- Clients connecting to wrong instances
- Session resume failures
- Inconsistent affinity headers

#### Investigation
```bash
# Check Nginx upstream status
curl -s http://nginx/nginx_status

# Check affinity cookie distribution
# Monitor X-Affinity-Key headers in logs

# Check Redis sticky routing data
redis-cli --scan --pattern "sticky:*"
```

## Monitoring and Alerts

### Critical Alerts
- `dropped_messages > 0` → Immediate escalation
- `resume_failures > 20` → High priority
- `rtt_p95_ms > 300` → Medium priority
- `ws_upgrades_blocked_during_drain > 0` during non-drain periods → Investigation needed

### Dashboard Queries
```promql
# WebSocket connection rate
rate(ws_connections_total[5m])

# Resume success rate
rate(ws_resumes[5m]) / (rate(ws_resumes[5m]) + rate(resume_failures[5m]))

# Message drop rate (should be 0)
rate(dropped_messages[5m])

# RTT percentiles
histogram_quantile(0.95, rate(ws_rtt_seconds_bucket[5m]))
```

## Recovery Scenarios

### Complete System Failure

#### Recovery Steps
1. **Restore from backup**
2. **Verify Redis data integrity**
3. **Restart all services**
4. **Monitor resume success rate**
5. **Validate zero-drop functionality**

### Time Synchronization Issues

#### Symptoms
- Authentication failures
- Resume timeouts

#### Resolution
```bash
# Check system time
timedatectl status

# Sync with NTP
ntpdate -s time.nist.gov

# Restart services if needed
```

## Performance Targets

### Zero-Drop Criteria
- **Message drops**: 0 during normal operations
- **Resume success rate**: >95%
- **RTT P95**: ≤150ms
- **Reconnection time**: ≤3 seconds
- **Drain completion**: Within grace period

### Capacity Limits
- **Max concurrent WebSocket connections**: 1000 per instance
- **Max resume buffer per session**: 200 messages
- **Resume store TTL**: 15 minutes
- **Sticky cookie TTL**: 1 hour

## Emergency Contacts

- **On-call Engineer**: [Contact Info]
- **Platform Team**: [Contact Info]
- **Infrastructure Team**: [Contact Info]

## Change Log

| Date | Change | Author |
|------|--------|--------|
| 2025-01-27 | Initial runbook | System |