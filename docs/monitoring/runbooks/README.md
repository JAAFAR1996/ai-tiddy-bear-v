# Conversation Service Runbooks

This directory contains operational runbooks for the AI Teddy Bear Conversation Service.

## Quick Reference

| Alert | Severity | Response Time | Primary Action |
|-------|----------|---------------|----------------|
| ConversationServiceDown | Critical | < 5 minutes | Check service health, restart if needed |
| CriticalSafetyIncident | Critical | < 2 minutes | Review incident, notify safety team |
| HighErrorRate | Warning | < 15 minutes | Check logs, identify error patterns |
| DatabaseConnectionIssues | Critical | < 5 minutes | Check DB connectivity, failover if needed |

## Runbook Index

### Service Health
- [Service Down Response](service-down.md)
- [High Latency Investigation](high-latency.md)
- [Error Rate Analysis](error-rate.md)

### Safety & Compliance
- [Safety Incident Response](safety-incident.md)
- [COPPA Violation Handling](coppa-violation.md)

### Infrastructure
- [Database Issues](database-issues.md)
- [Redis Cache Problems](redis-issues.md)
- [Memory Usage Investigation](memory-usage.md)

### Performance
- [Capacity Planning](capacity-planning.md)
- [Deadlock Resolution](deadlock-resolution.md)

## Emergency Contacts

### Primary On-Call
- Backend Team: backend-oncall@example.com
- Safety Team: safety-team@example.com
- Infrastructure: infra-oncall@example.com

### Escalation
- Engineering Manager: eng-manager@example.com
- CTO: cto@example.com

## Common Commands

```bash
# Check service status
kubectl get pods -l app=conversation-service

# View recent logs
kubectl logs -l app=conversation-service --tail=100

# Check metrics
curl http://conversation-service:8000/metrics

# Health check
curl http://conversation-service:8000/health
```
