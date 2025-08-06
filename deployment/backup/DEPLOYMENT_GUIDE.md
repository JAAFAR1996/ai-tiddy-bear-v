# AI Teddy Bear Backup Services Deployment Guide

This guide provides comprehensive instructions for deploying the AI Teddy Bear backup and restore system in production environments.

## Overview

The backup system consists of multiple components:
- **Backup Orchestrator**: Manages backup operations and coordination
- **Backup Scheduler**: Handles scheduled backup jobs with cron-like functionality
- **Backup Monitor**: Provides monitoring, alerting, and COPPA compliance reporting
- **Testing Framework**: Automated testing of backup and restore operations
- **Metrics Exporter**: Prometheus metrics for monitoring and alerting

## Prerequisites

### System Requirements
- Kubernetes cluster (v1.20+)
- Docker container runtime
- Persistent storage (500GB+ recommended)
- PostgreSQL database for metadata
- Redis for job coordination
- Prometheus for monitoring (optional)

### Security Requirements
- Encryption keys for backup data
- COPPA encryption keys for child data
- Database credentials
- Cloud storage credentials (AWS S3, Azure, etc.)
- SMTP credentials for alerts
- Webhook URLs for notifications

## Quick Start

### 1. Environment Setup

Create the necessary environment variables:

```bash
# Backup encryption keys (generate secure keys)
export BACKUP_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
export COPPA_ENCRYPTION_KEY=$(python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")

# Database configuration
export DATABASE_BACKUP_URL="postgresql://backup_user:secure_password@postgres:5432/backup_metadata"
export BACKUP_DB_PASSWORD="secure_database_password"

# Redis configuration
export BACKUP_REDIS_PASSWORD="secure_redis_password"

# Cloud storage (choose your provider)
export AWS_BACKUP_ACCESS_KEY_ID="your_aws_key"
export AWS_BACKUP_SECRET_ACCESS_KEY="your_aws_secret"
export S3_BACKUP_BUCKET="ai-teddy-backups"

# Notification settings
export ALERT_EMAIL_FROM="backup-alerts@ai-teddybear.com"
export ALERT_EMAIL_TO="ops-team@ai-teddybear.com"
export BACKUP_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
```

### 2. Docker Compose Deployment (Development/Testing)

```bash
# Clone the repository
git clone https://github.com/ai-teddy-bear/backup-system.git
cd backup-system

# Create data directories
mkdir -p data/backups logs/backup keys

# Generate and store encryption keys
echo "$BACKUP_ENCRYPTION_KEY" > keys/backup.key
echo "$COPPA_ENCRYPTION_KEY" > keys/coppa.key
chmod 600 keys/*.key

# Deploy with Docker Compose
docker-compose -f deployment/backup/docker-compose.backup.yml up -d

# Verify deployment
docker-compose -f deployment/backup/docker-compose.backup.yml ps
```

### 3. Kubernetes Deployment (Production)

```bash
# Create namespace
kubectl create namespace ai-teddy-backup

# Create secrets (base64 encode your values)
kubectl create secret generic backup-secrets \
  --from-literal=BACKUP_ENCRYPTION_KEY=$(echo -n "$BACKUP_ENCRYPTION_KEY" | base64) \
  --from-literal=COPPA_ENCRYPTION_KEY=$(echo -n "$COPPA_ENCRYPTION_KEY" | base64) \
  --from-literal=DATABASE_BACKUP_URL=$(echo -n "$DATABASE_BACKUP_URL" | base64) \
  --from-literal=AWS_BACKUP_ACCESS_KEY_ID=$(echo -n "$AWS_BACKUP_ACCESS_KEY_ID" | base64) \
  --from-literal=AWS_BACKUP_SECRET_ACCESS_KEY=$(echo -n "$AWS_BACKUP_SECRET_ACCESS_KEY" | base64) \
  -n ai-teddy-backup

# Deploy backup services
kubectl apply -f deployment/backup/kubernetes/backup-services.yaml

# Check deployment status
kubectl get pods -n ai-teddy-backup
kubectl get services -n ai-teddy-backup
```

## Configuration

### Backup Configuration

Edit the ConfigMap in `deployment/backup/kubernetes/backup-services.yaml`:

```yaml
data:
  backup.conf: |
    # Backup retention policies
    BACKUP_RETENTION_DAYS=90
    
    # Backup types enabled
    HOURLY_BACKUP_ENABLED=true
    DAILY_BACKUP_ENABLED=true
    WEEKLY_BACKUP_ENABLED=true
    MONTHLY_BACKUP_ENABLED=true
    
    # Performance settings
    BACKUP_PARALLEL_JOBS=2
    BACKUP_CHUNK_SIZE_MB=100
    BACKUP_TIMEOUT_MINUTES=120
    
    # Compliance settings
    COPPA_COMPLIANCE_MODE=true
    BACKUP_ENCRYPTION_ENABLED=true
    
    # Testing configuration
    BACKUP_TESTING_ENABLED=true
```

### Storage Providers

Configure multiple storage backends for redundancy:

#### AWS S3
```bash
export AWS_BACKUP_ACCESS_KEY_ID="your_access_key"
export AWS_BACKUP_SECRET_ACCESS_KEY="your_secret_key"
export AWS_BACKUP_REGION="us-east-1"
export S3_BACKUP_BUCKET="ai-teddy-backups"
```

#### Azure Blob Storage
```bash
export AZURE_BACKUP_CONNECTION_STRING="DefaultEndpointsProtocol=https;AccountName=...;AccountKey=...;EndpointSuffix=core.windows.net"
export AZURE_BACKUP_CONTAINER="backups"
```

#### MinIO (Self-hosted)
```bash
export MINIO_BACKUP_ENDPOINT="https://minio.your-domain.com"
export MINIO_BACKUP_ACCESS_KEY="minio_access_key"
export MINIO_BACKUP_SECRET_KEY="minio_secret_key"
export MINIO_BACKUP_BUCKET="backups"
```

### Notification Channels

#### Email Notifications
```bash
export ALERT_EMAIL_ENABLED=true
export ALERT_EMAIL_SMTP_SERVER="smtp.gmail.com:587"
export ALERT_EMAIL_FROM="backup-alerts@ai-teddybear.com"
export ALERT_EMAIL_TO="ops-team@ai-teddybear.com,security@ai-teddybear.com"
```

#### Slack Integration
```bash
export BACKUP_SLACK_WEBHOOK_URL="https://hooks.slack.com/services/T00000000/B00000000/XXXXXXXXXXXXXXXXXXXXXXXX"
```

#### PagerDuty Integration
```bash
export BACKUP_PAGERDUTY_KEY="your-pagerduty-integration-key"
```

## Monitoring and Alerting

### Prometheus Integration

The backup services expose metrics on port 9090. Add this to your Prometheus configuration:

```yaml
scrape_configs:
  - job_name: 'backup-services'
    static_configs:
      - targets: ['backup-orchestrator-service:9090']
    scrape_interval: 30s
    metrics_path: /metrics
```

### Key Metrics to Monitor

- `backup_operations_total`: Total backup operations by status
- `backup_duration_seconds`: Backup operation duration
- `backup_size_bytes`: Size of backup files
- `storage_usage_percentage`: Storage utilization
- `coppa_compliance_rate`: COPPA compliance percentage
- `backup_alerts_total`: Number of backup alerts
- `sla_rto_actual_minutes`: Recovery Time Objective
- `sla_rpo_actual_minutes`: Recovery Point Objective

### Grafana Dashboards

Import the provided dashboard configuration:

```bash
kubectl apply -f deployment/backup/config/grafana/dashboards/
```

## Testing and Validation

### Manual Testing

```bash
# Run backup integrity tests
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python /app/scripts/backup_test_runner.py --suite backup_integrity

# Run restore functionality tests
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python /app/scripts/backup_test_runner.py --suite restore_functionality

# Run COPPA compliance tests
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python /app/scripts/backup_test_runner.py --suite coppa_compliance

# Run full test suite
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python /app/scripts/backup_test_runner.py --all
```

### Automated Testing

The system includes a CronJob for automated testing:

```bash
# Check scheduled test job
kubectl get cronjob backup-testing -n ai-teddy-backup

# Manually trigger test job
kubectl create job --from=cronjob/backup-testing manual-test -n ai-teddy-backup

# Check test results
kubectl logs job/manual-test -n ai-teddy-backup
```

### Disaster Recovery Testing

```bash
# Run disaster recovery drill
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python /app/scripts/backup_test_runner.py --dr-drill
```

## Backup Operations

### Manual Backup

```bash
# Trigger immediate backup
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python -c "
from src.infrastructure.backup.orchestrator import BackupOrchestrator
import asyncio
async def backup():
    orchestrator = BackupOrchestrator()
    await orchestrator.schedule_backup(job)
asyncio.run(backup())
"
```

### Backup Status

```bash
# Check backup status via API
kubectl port-forward service/backup-orchestrator-service 8080:9090 -n ai-teddy-backup &
curl http://localhost:8080/status
```

### List Backups

```bash
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python -c "
from src.infrastructure.backup.database_backup import DatabaseBackupService
import asyncio
async def list_backups():
    service = DatabaseBackupService('connection_string', '/app/backups')
    backups = await service.list_backups()
    for backup in backups:
        print(f'{backup.backup_id}: {backup.timestamp} ({backup.size_bytes} bytes)')
asyncio.run(list_backups())
"
```

## Restore Operations

### Database Restore

```bash
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python -c "
from src.infrastructure.backup.restore_service import RestoreService, RestoreRequest, RestoreType
import asyncio
async def restore():
    service = RestoreService(db_service, file_service, config_service, 'encryption_key')
    request = RestoreRequest(
        restore_id='manual_restore_001',
        restore_type=RestoreType.DATABASE_FULL,
        backup_ids=['backup_id_here'],
        dry_run=True  # Remove for actual restore
    )
    result = await service.restore(request)
    print(f'Restore status: {result.status}')
asyncio.run(restore())
"
```

### File Restore

```bash
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python -c "
from src.infrastructure.backup.restore_service import RestoreService, RestoreRequest, RestoreType
import asyncio
async def restore():
    service = RestoreService(db_service, file_service, config_service, 'encryption_key')
    request = RestoreRequest(
        restore_id='file_restore_001',
        restore_type=RestoreType.FILES_FULL,
        backup_ids=['backup_id_here'],
        dry_run=True
    )
    result = await service.restore(request)
    print(f'Restore status: {result.status}')
asyncio.run(restore())
"
```

## COPPA Compliance

### Compliance Monitoring

The system automatically generates COPPA compliance reports:

```bash
# Check compliance status
kubectl logs -f deployment/backup-monitor -n ai-teddy-backup | grep -i coppa

# Generate compliance report
kubectl exec -n ai-teddy-backup deployment/backup-monitor -- \
  python -c "
from src.infrastructure.backup.monitoring import BackupMonitoringService
from datetime import datetime, timedelta
import asyncio
async def compliance_report():
    monitor = BackupMonitoringService(None, {}, {})
    end_time = datetime.utcnow()
    start_time = end_time - timedelta(days=30)
    report = await monitor.generate_compliance_report(start_time, end_time)
    print(f'Compliance rate: {report.compliance_rate:.2%}')
    print(f'Total backups: {report.total_backups}')
    print(f'Compliant backups: {report.compliant_backups}')
    if report.issues:
        print('Issues:', report.issues)
asyncio.run(compliance_report())
"
```

### Data Encryption Verification

```bash
# Verify backup encryption
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  find /app/backups -name "*.enc" -type f | head -10
```

## Troubleshooting

### Common Issues

#### 1. Backup Failures

```bash
# Check backup orchestrator logs
kubectl logs deployment/backup-orchestrator -n ai-teddy-backup

# Check scheduler logs
kubectl logs deployment/backup-scheduler -n ai-teddy-backup

# Check for storage issues
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- df -h /app/backups
```

#### 2. Database Connection Issues

```bash
# Check database connectivity
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  pg_isready -h postgres -p 5432 -U backup_user

# Test database connection
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  psql $DATABASE_BACKUP_URL -c "SELECT version();"
```

#### 3. Storage Provider Issues

```bash
# Test AWS S3 connectivity
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  aws s3 ls s3://$S3_BACKUP_BUCKET --region $AWS_BACKUP_REGION

# Test Azure connectivity
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  az storage container list --connection-string "$AZURE_BACKUP_CONNECTION_STRING"
```

#### 4. Encryption Issues

```bash
# Verify encryption keys are accessible
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  python -c "
from cryptography.fernet import Fernet
import os
key = os.getenv('BACKUP_ENCRYPTION_KEY')
if key:
    f = Fernet(key.encode())
    test_data = b'test encryption'
    encrypted = f.encrypt(test_data)
    decrypted = f.decrypt(encrypted)
    print('Encryption test:', 'PASS' if decrypted == test_data else 'FAIL')
else:
    print('BACKUP_ENCRYPTION_KEY not found')
"
```

### Log Analysis

```bash
# Backup operation logs
kubectl logs -f deployment/backup-orchestrator -n ai-teddy-backup | grep -E "(ERROR|WARN|backup)"

# Compliance monitoring logs
kubectl logs -f deployment/backup-monitor -n ai-teddy-backup | grep -E "(compliance|COPPA)"

# Performance metrics
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- \
  curl -s http://localhost:9090/metrics | grep backup_duration
```

### Health Checks

```bash
# Run comprehensive health check
kubectl exec -n ai-teddy-backup deployment/backup-orchestrator -- /app/healthcheck.sh

# Check service status
kubectl get pods -n ai-teddy-backup -o wide

# Check resource usage
kubectl top pods -n ai-teddy-backup
```

## Security Considerations

### Encryption

- All backup data is encrypted using AES-256
- Child data uses separate COPPA-compliant encryption keys
- Encryption keys should be stored in Kubernetes secrets
- Regular key rotation is recommended

### Access Controls

- Use Kubernetes RBAC for service access
- Limit network access with NetworkPolicies
- Run containers as non-root users
- Use service accounts with minimal permissions

### Compliance

- COPPA compliance monitoring is built-in
- Audit logs track all backup/restore operations
- Data retention policies are automatically enforced
- Regular compliance reports are generated

## Performance Tuning

### Backup Performance

```yaml
# Adjust parallel jobs based on system capacity
BACKUP_PARALLEL_JOBS: "4"

# Optimize chunk size for your network
BACKUP_CHUNK_SIZE_MB: "200"

# Increase timeout for large databases
BACKUP_TIMEOUT_MINUTES: "240"
```

### Resource Allocation

```yaml
resources:
  requests:
    memory: "1Gi"
    cpu: "500m"
  limits:
    memory: "4Gi"
    cpu: "2000m"
```

### Storage Optimization

- Use SSD storage for better I/O performance
- Configure appropriate backup retention
- Implement compression for space savings
- Use incremental backups where possible

## Maintenance

### Regular Tasks

1. **Monitor storage usage** - Set up alerts for storage capacity
2. **Review compliance reports** - Ensure COPPA compliance
3. **Test restore procedures** - Verify backup integrity
4. **Update encryption keys** - Rotate keys periodically
5. **Clean up old backups** - Remove expired backups
6. **Monitor performance** - Check backup/restore times

### Updates and Upgrades

```bash
# Update to latest image
kubectl set image deployment/backup-orchestrator \
  backup-orchestrator=ai-teddy-bear/backup-services:v1.2.0 \
  -n ai-teddy-backup

# Monitor rollout
kubectl rollout status deployment/backup-orchestrator -n ai-teddy-backup
```

## Support

For issues and support:

1. Check the logs and metrics
2. Review the troubleshooting section
3. Run health checks and tests
4. Create an issue in the GitHub repository
5. Contact the development team

## License

This backup system is part of the AI Teddy Bear application and follows the same licensing terms.