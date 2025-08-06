# AI Teddy Bear Production Deployment Guide

## Table of Contents
1. [Prerequisites](#prerequisites)
2. [Infrastructure Setup](#infrastructure-setup)
3. [Environment Configuration](#environment-configuration)
4. [Deployment Process](#deployment-process)
5. [Post-Deployment Verification](#post-deployment-verification)
6. [Monitoring and Maintenance](#monitoring-and-maintenance)
7. [Troubleshooting](#troubleshooting)
8. [Security Considerations](#security-considerations)

## Prerequisites

### System Requirements
- **Docker**: Version 20.10 or higher
- **Docker Compose**: Version 2.0 or higher
- **Server**: Minimum 4GB RAM, 2 CPU cores, 50GB storage
- **Operating System**: Linux (Ubuntu 20.04+ recommended)
- **Network**: SSL certificate for HTTPS
- **Database**: PostgreSQL 15+ (managed service recommended)
- **Cache**: Redis 7+ (managed service recommended)

### Required Accounts & Services
- **Domain**: Registered domain with DNS control
- **SSL Certificate**: Valid SSL certificate (Let's Encrypt recommended)
- **Email Service**: SMTP service for notifications
- **Cloud Storage**: S3-compatible storage for audio files
- **Monitoring**: Application monitoring service (optional)

### Required Environment Variables
Create a `.env.production` file with the following variables:

```bash
# Application Configuration
APP_ENV=production
APP_DEBUG=false
APP_SECRET_KEY=your-secret-key-here
APP_DOMAIN=yourdomain.com
APP_PORT=8000

# Database Configuration
DATABASE_URL=postgresql://user:password@host:5432/ai_teddy_bear
DATABASE_POOL_SIZE=10
DATABASE_POOL_TIMEOUT=30

# Redis Configuration
REDIS_URL=redis://redis:6379/0
REDIS_PASSWORD=your-redis-password

# Security Configuration
JWT_SECRET_KEY=your-jwt-secret-key
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS Configuration
ALLOWED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
ALLOWED_METHODS=GET,POST,PUT,DELETE
ALLOWED_HEADERS=*

# Email Configuration
SMTP_HOST=smtp.youremailservice.com
SMTP_PORT=587
SMTP_USERNAME=your-email@domain.com
SMTP_PASSWORD=your-email-password
SMTP_TLS=true

# Storage Configuration
S3_BUCKET_NAME=ai-teddy-audio-files
S3_ACCESS_KEY=your-s3-access-key
S3_SECRET_KEY=your-s3-secret-key
S3_REGION=us-east-1

# AI Service Configuration
OPENAI_API_KEY=your-openai-api-key
AZURE_SPEECH_API_KEY=your-azure-speech-key
AZURE_SPEECH_REGION=eastus

# Safety Configuration
SAFETY_FILTER_LEVEL=strict
COPPA_COMPLIANCE_MODE=true
CONTENT_MODERATION_LEVEL=high

# Monitoring Configuration
SENTRY_DSN=your-sentry-dsn
LOG_LEVEL=INFO
METRICS_ENABLED=true
```

## Infrastructure Setup

### 1. Server Preparation

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Create application directory
sudo mkdir -p /opt/ai-teddy-bear
sudo chown $USER:$USER /opt/ai-teddy-bear
cd /opt/ai-teddy-bear
```

### 2. Firewall Configuration

```bash
# Configure UFW firewall
sudo ufw enable
sudo ufw allow ssh
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw reload
```

### 3. SSL Certificate Setup

```bash
# Install Certbot for Let's Encrypt
sudo apt install certbot python3-certbot-nginx -y

# Obtain SSL certificate
sudo certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com

# Set up auto-renewal
sudo crontab -e
# Add line: 0 12 * * * /usr/bin/certbot renew --quiet
```

## Environment Configuration

### 1. Clone Repository

```bash
cd /opt/ai-teddy-bear
git clone https://github.com/yourusername/ai-teddy-bear.git .
git checkout main
```

### 2. Configure Environment

```bash
# Copy production environment file
cp .env.example .env.production

# Edit environment variables
nano .env.production
# Fill in all required values from the prerequisites section

# Set proper permissions
chmod 600 .env.production
```

### 3. SSL Certificate Integration

```bash
# Create SSL directory
mkdir -p ssl/

# Copy SSL certificates
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem ssl/
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem ssl/
sudo chown $USER:$USER ssl/*
```

## Deployment Process

### 1. Pre-Deployment Checks

```bash
# Run pre-deployment validation
./scripts/production/deploy.sh --validate-only

# Check environment configuration
./scripts/production/deploy.sh --check-env

# Verify SSL certificates
./scripts/production/deploy.sh --check-ssl
```

### 2. Initial Deployment

```bash
# Build and deploy application
./scripts/production/deploy.sh --initial

# This script will:
# - Build Docker images
# - Start all services
# - Run database migrations
# - Initialize data
# - Perform health checks
```

### 3. Database Setup

```bash
# The deployment script automatically runs migrations, but if needed manually:

# Run database migrations
docker-compose -f docker-compose.production.yml exec app python -m alembic upgrade head

# Create initial admin user
docker-compose -f docker-compose.production.yml exec app python scripts/create_admin.py

# Verify database setup
docker-compose -f docker-compose.production.yml exec app python scripts/verify_database.py
```

### 4. Service Verification

```bash
# Check all services are running
docker-compose -f docker-compose.production.yml ps

# Check service logs
docker-compose -f docker-compose.production.yml logs app
docker-compose -f docker-compose.production.yml logs postgres
docker-compose -f docker-compose.production.yml logs redis
docker-compose -f docker-compose.production.yml logs nginx
```

## Post-Deployment Verification

### 1. Health Checks

```bash
# Run comprehensive health check
./scripts/production/health_check.sh

# Manual health check endpoints
curl -k https://yourdomain.com/health
curl -k https://yourdomain.com/api/v1/health
curl -k https://yourdomain.com/api/v1/health/database
curl -k https://yourdomain.com/api/v1/health/redis
```

### 2. Security Verification

```bash
# Run security audit
./scripts/production/security_audit.sh

# Test SSL configuration
openssl s_client -connect yourdomain.com:443 -servername yourdomain.com

# Verify security headers
curl -I https://yourdomain.com
```

### 3. Performance Testing

```bash
# Run performance tests
docker-compose -f docker-compose.production.yml exec app python -m pytest tests_consolidated/test_integration.py::TestPerformanceIntegration -v

# Load testing (optional)
# Install Apache Bench: sudo apt install apache2-utils
ab -n 100 -c 10 https://yourdomain.com/health
```

### 4. Functional Testing

```bash
# Run end-to-end tests
docker-compose -f docker-compose.production.yml exec app python -m pytest tests_consolidated/test_e2e.py -v

# Test key user journeys
docker-compose -f docker-compose.production.yml exec app python scripts/test_user_journey.py
```

## Monitoring and Maintenance

### 1. Log Management

```bash
# View application logs
docker-compose -f docker-compose.production.yml logs -f app

# View nginx logs
docker-compose -f docker-compose.production.yml logs -f nginx

# Set up log rotation
sudo nano /etc/logrotate.d/ai-teddy-bear
```

Log rotation configuration:
```
/opt/ai-teddy-bear/logs/*.log {
    daily
    missingok
    rotate 30
    compress
    delaycompress
    notifempty
    create 644 root root
    postrotate
        docker-compose -f /opt/ai-teddy-bear/docker-compose.production.yml restart nginx
    endscript
}
```

### 2. Database Maintenance

```bash
# Database backup (automated via cron)
./scripts/production/backup.sh

# Manual backup
docker-compose -f docker-compose.production.yml exec postgres pg_dump -U postgres ai_teddy_bear > backup_$(date +%Y%m%d).sql

# Database optimization
docker-compose -f docker-compose.production.yml exec postgres psql -U postgres -d ai_teddy_bear -c "VACUUM ANALYZE;"
```

### 3. Application Updates

```bash
# Standard update process
./scripts/production/update.sh

# Manual update process:
git pull origin main
./scripts/production/deploy.sh --update
```

### 4. Monitoring Setup

Add to crontab for automated monitoring:
```bash
# Health check every 5 minutes
*/5 * * * * /opt/ai-teddy-bear/scripts/production/health_check.sh

# Database backup daily at 2 AM
0 2 * * * /opt/ai-teddy-bear/scripts/production/backup.sh

# SSL certificate renewal check monthly
0 0 1 * * /usr/bin/certbot renew --quiet --post-hook "docker-compose -f /opt/ai-teddy-bear/docker-compose.production.yml restart nginx"

# Disk space check daily
0 6 * * * df -h / | grep -vE '^Filesystem|tmpfs|cdrom' | awk '{if($5 >= "80%") print "Warning: " $0}'
```

## Troubleshooting

### Common Issues

#### 1. Service Won't Start

```bash
# Check service status
docker-compose -f docker-compose.production.yml ps

# Check logs for errors
docker-compose -f docker-compose.production.yml logs app

# Check resource usage
docker stats

# Restart specific service
docker-compose -f docker-compose.production.yml restart app
```

#### 2. Database Connection Issues

```bash
# Check database connectivity
docker-compose -f docker-compose.production.yml exec app python -c "from src.infrastructure.database.connection import DatabaseConnection; print('DB OK')"

# Check database status
docker-compose -f docker-compose.production.yml exec postgres pg_isready

# Reset database connection pool
docker-compose -f docker-compose.production.yml restart app
```

#### 3. SSL Certificate Issues

```bash
# Check certificate validity
openssl x509 -in ssl/fullchain.pem -text -noout

# Renew certificate
sudo certbot renew --force-renewal

# Update certificate in container
cp /etc/letsencrypt/live/yourdomain.com/* ssl/
docker-compose -f docker-compose.production.yml restart nginx
```

#### 4. Performance Issues

```bash
# Check resource usage
docker stats
htop

# Check database performance
docker-compose -f docker-compose.production.yml exec postgres psql -U postgres -d ai_teddy_bear -c "SELECT * FROM pg_stat_activity;"

# Restart services to clear memory
docker-compose -f docker-compose.production.yml restart
```

### Emergency Procedures

#### 1. Complete System Failure

```bash
# Stop all services
docker-compose -f docker-compose.production.yml down

# Check system resources
df -h
free -m

# Restart system if needed
sudo reboot

# Start services after reboot
cd /opt/ai-teddy-bear
docker-compose -f docker-compose.production.yml up -d
```

#### 2. Data Recovery

```bash
# Restore from backup
./scripts/production/restore.sh backup_20231201.sql

# Verify data integrity
docker-compose -f docker-compose.production.yml exec app python scripts/verify_database.py
```

#### 3. Rollback Deployment

```bash
# Rollback to previous version
./scripts/production/rollback.sh

# Manual rollback
git checkout previous-stable-tag
./scripts/production/deploy.sh --rollback
```

## Security Considerations

### 1. Regular Security Updates

```bash
# Update system packages monthly
sudo apt update && sudo apt upgrade -y

# Update Docker images monthly
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d --force-recreate
```

### 2. Security Monitoring

```bash
# Run security audit weekly
./scripts/production/security_audit.sh

# Check for vulnerabilities
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy image ai-teddy-bear:latest
```

### 3. Access Control

```bash
# Regular review of user access
docker-compose -f docker-compose.production.yml exec app python scripts/audit_users.py

# Review system access logs
sudo journalctl -u ssh -n 100
```

### 4. Data Protection

```bash
# Encrypt sensitive data at rest
# Ensure all environment variables containing secrets are properly secured

# Regular backup verification
./scripts/production/verify_backup.sh

# Test disaster recovery procedures quarterly
./scripts/production/disaster_recovery_test.sh
```

## Maintenance Schedule

### Daily
- Automated health checks
- Log rotation
- Backup verification

### Weekly  
- Security audit
- Performance review
- Error log analysis

### Monthly
- System package updates
- Docker image updates
- SSL certificate check
- Capacity planning review

### Quarterly
- Disaster recovery testing
- Security penetration testing
- Performance optimization review
- Documentation updates

## Support Contacts

- **Emergency Contact**: [Your emergency contact]
- **DevOps Team**: [Your DevOps contact]
- **Security Team**: [Your security contact]
- **Monitoring Alerts**: [Your monitoring system]

## Documentation Updates

This deployment guide should be updated whenever:
- New environment variables are added
- Deployment procedures change
- New services are added
- Security requirements change

Last Updated: [Current Date]
Version: 1.0.0
