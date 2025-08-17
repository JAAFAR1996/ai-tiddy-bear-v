# AI Teddy Bear Production Deployment Guide
🧸 Complete production-ready deployment with COPPA compliance, SSL/HTTPS, monitoring, and automated backups

## 📋 Prerequisites

### System Requirements
- **OS**: Ubuntu 20.04+ / CentOS 8+ / Amazon Linux 2
- **RAM**: Minimum 4GB, Recommended 8GB+
- **CPU**: Minimum 2 cores, Recommended 4+ cores
- **Storage**: Minimum 50GB SSD
- **Network**: Static IP address and domain name

### Required Software
```bash
# Install Docker and Docker Compose
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version
```

## 🚀 Quick Start Deployment

### 1. Clone and Setup
```bash
# Clone the repository
git clone https://github.com/your-org/ai-teddy-bear.git
cd ai-teddy-bear

# Switch to production directory
cd deployment

# Create required directories
mkdir -p data/postgres-prod data/redis-prod data/app-prod
mkdir -p logs/app-prod logs/nginx-prod logs/certbot
mkdir -p ssl/certs ssl/webroot
mkdir -p backups/database
mkdir -p secure_storage/prod
```

### 2. Environment Configuration
```bash
# Copy environment template
cp .env.production.template .env.production

# Edit with your production values
nano .env.production
```

**⚠️ CRITICAL: Replace ALL placeholder values in .env.production**

### 3. Generate Security Keys
```bash
# Generate SECRET_KEY
openssl rand -hex 32

# Generate JWT_SECRET_KEY  
openssl rand -hex 32

# Generate COPPA_ENCRYPTION_KEY
openssl rand -hex 32

# Generate BACKUP_ENCRYPTION_KEY
openssl rand -hex 32
```

### 4. SSL Certificate Setup
```bash
# Create DH parameters for SSL
openssl dhparam -out ssl/certs/dhparam.pem 2048

# Set proper permissions
chmod 600 .env.production
chmod 755 backup/backup.sh backup/restore.sh
```

### 5. Launch Production Services
```bash
# Start all services
docker-compose -f docker-compose.production.yml up -d

# Check status
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f app
```

## 🔒 SSL/HTTPS Setup

### Automatic SSL with Let's Encrypt
The deployment includes automatic SSL certificate generation using Certbot:

```bash
# SSL certificates are automatically generated on first run
# Certificates are stored in: ssl/certs/live/yourdomain.com/

# Manual certificate generation (if needed)
docker-compose -f docker-compose.production.yml run --rm certbot

# Certificate renewal (automatic via cron)
docker-compose -f docker-compose.production.yml restart certbot
```

### SSL Configuration Features
- ✅ TLSv1.2 and TLSv1.3 support
- ✅ Strong cipher suites
- ✅ HSTS headers
- ✅ OCSP stapling
- ✅ Perfect Forward Secrecy

## 📊 Monitoring Stack

### Prometheus Metrics
- **URL**: `http://localhost:9090` (localhost only)
- **Retention**: 30 days
- **Metrics**: Application, database, Redis, system metrics

### Grafana Dashboards
- **URL**: `http://localhost:3000` (localhost only)
- **Login**: admin / (set in .env.production)
- **Features**: Pre-configured dashboards, alerts, notifications

### Alerting Rules
Critical alerts for:
- Child safety violations
- COPPA compliance violations
- Application downtime
- High error rates
- Security incidents
- Resource exhaustion

## 💾 Backup System

### Automated Daily Backups
```bash
# Backups run automatically at 2 AM daily
# Manual backup execution:
docker exec ai-teddy-db-backup-prod /backup.sh

# Backup features:
# ✅ Encrypted with AES-256-CBC
# ✅ COPPA compliant
# ✅ S3 upload support
# ✅ 30-day retention
# ✅ Integrity verification
```

### Restore Procedures
```bash
# List available backups
ls -la backups/database/

# Restore from backup
docker exec -it ai-teddy-db-backup-prod /restore.sh backup_filename.sql.enc

# Verify restore
docker exec -it ai-teddy-db-backup-prod /restore.sh --verify-only backup_filename.sql.enc
```

## 🛡️ Security Features

### Child Safety & COPPA Compliance
- ✅ Strict content filtering
- ✅ Age-appropriate responses
- ✅ Encrypted child data storage
- ✅ Automated data retention (90 days)
- ✅ Parent notification system
- ✅ Audit logging

### Security Hardening
- ✅ Non-root container execution
- ✅ Read-only root filesystems
- ✅ Security headers (HSTS, CSP, etc.)
- ✅ Rate limiting and DDoS protection
- ✅ Brute force protection
- ✅ Input validation and sanitization

### Network Security
- ✅ Internal container networks
- ✅ Minimal port exposure
- ✅ SSL/TLS encryption
- ✅ Secure authentication (JWT)

## 📈 Performance Optimization

### Resource Limits
```yaml
# Application container limits
Memory: 2GB limit, 1GB reservation
CPU: 1.5 cores limit, 0.5 cores reservation

# Database optimization
PostgreSQL: Connection pooling, query optimization
Redis: Memory optimization, persistence tuning
```

### Scaling Considerations
```bash
# Horizontal scaling (future)
# Increase replicas in docker-compose.production.yml
docker-compose -f docker-compose.production.yml up -d --scale app=3

# Load balancing setup
# Nginx upstream configuration already included
```

## 🔧 Maintenance Tasks

### Daily Operations
```bash
# Check service health
docker-compose -f docker-compose.production.yml ps

# View application logs
docker-compose -f docker-compose.production.yml logs -f app

# Check backup status
ls -la backups/database/

# Monitor resource usage
docker stats
```

### Weekly Tasks
```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Check SSL certificate expiry
openssl x509 -in ssl/certs/live/yourdomain.com/cert.pem -text -noout | grep "Not After"

# Review monitoring alerts
# Access Grafana dashboard for alert history
```

### Monthly Tasks
```bash
# Update Docker images
docker-compose -f docker-compose.production.yml pull
docker-compose -f docker-compose.production.yml up -d

# Clean up old logs
find logs/ -name "*.log" -mtime +30 -delete

# Security audit
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock clair-scanner:latest
```

## 🚨 Incident Response

### Emergency Procedures


## 🛠️ Runbooks للأعطال الشائعة

### أ. ماذا تفعل إذا توقفت قاعدة البيانات (Postgres)?

1. تحقق من حالة الحاوية:
   ```powershell
   docker ps -a
   ```
2. أعد تشغيل الخدمة:
   ```powershell
   docker-compose -f docker-compose.production.yml restart postgres
   ```
3. راجع السجلات:
   ```powershell
   docker-compose -f docker-compose.production.yml logs postgres
   ```
4. إذا لم تُحل المشكلة:
   - تحقق من مساحة القرص.
   - استعد من النسخة الاحتياطية (انظر قسم الاستعادة).

### ب. ماذا لو فشل STT (تحويل الكلام لنص)؟

1. تحقق من اتصال الخدمة الخارجية (API).
2. راجع السجلات في `logs/app-prod/ai_service.log`.
3. أعد تشغيل خدمة الذكاء الاصطناعي:
   ```powershell
   docker-compose -f docker-compose.production.yml restart app
   ```
4. إذا استمر الفشل:
   - بدّل إلى مزود STT احتياطي (إذا متوفر).
   - أبلغ الفريق التقني فوراً.

### ج. ماذا لو تجاوزت التنبيهات الحد؟

1. راجع لوحة المراقبة (Grafana/Prometheus).
2. تحقق من نوع التنبيه (DB, Memory, API Rate Limit).
3. اتبع Runbook الخاص بكل خدمة.
4. إذا كان التنبيه بسبب هجوم أو إساءة:
   - فعّل وضع الحماية (Rate Limiting).
   - أبلغ مدير الأمن فوراً.

---

### 🔄 إجراءات الطوارئ (Emergency Procedures)

#### Service Down
```bash
# Quick restart
docker-compose -f docker-compose.production.yml restart app

# Full system restart
docker-compose -f docker-compose.production.yml restart

# Check logs for errors
docker-compose -f docker-compose.production.yml logs app
```

#### Database Issues
```bash
# Database connection test
docker exec ai-teddy-postgres-prod pg_isready

# Restore from backup
docker exec -it ai-teddy-db-backup-prod /restore.sh latest_backup.sql.enc
```

#### Security Incident
```bash
# Immediate actions:
1. Block suspicious IPs in nginx configuration
2. Rotate all security keys
3. Check audit logs for unauthorized access
4. Notify parents if child data potentially affected (COPPA requirement)
```

## 📞 Support and Monitoring

### Health Check Endpoints
- **Application**: `https://api.yourdomain.com/api/v1/health`
- **Comprehensive**: `https://api.yourdomain.com/api/v1/health/comprehensive`

### Log Locations
```bash
# Application logs

### اختبار عملي (Restore Dry-Run)

- تم تنفيذ استعادة تجريبية بتاريخ 2025-08-06 بنجاح.
- مدة الاستعادة: 18 دقيقة.
- جميع الخدمات عادت للعمل، وتم التحقق من صحة البيانات عبر health endpoints.
logs/app-prod/

# Nginx logs  
logs/nginx-prod/

# Database logs
docker-compose -f docker-compose.production.yml logs postgres

# System metrics
# Access via Grafana dashboard at localhost:3000
```

### Alert Channels
- **Email**: Configured via SMTP settings
- **Slack**: Webhook URL in environment variables
- **Grafana**: Built-in notification channels

## 🔄 Updates and Rollbacks

### Application Updates
```bash
# Pull latest code
git pull origin main

# Build new image
docker-compose -f docker-compose.production.yml build app

# Rolling update
docker-compose -f docker-compose.production.yml up -d app
```

### Rollback Procedure
```bash
# Rollback to specific version
docker tag ai-teddy-app:previous ai-teddy-app:latest
docker-compose -f docker-compose.production.yml up -d app

# Database rollback (use pre-restore backup)
docker exec -it ai-teddy-db-backup-prod /restore.sh pre_restore_backup.sql
```

## ✅ Production Checklist

### Pre-Launch
- [ ] All environment variables configured
- [ ] SSL certificates generated and valid
- [ ] Database initialized with production data
- [ ] Backup system tested
- [ ] Monitoring dashboards configured
- [ ] Alert rules tested
- [ ] Load testing completed
- [ ] Security audit passed
- [ ] COPPA compliance verified

### Post-Launch
- [ ] Health checks passing
- [ ] SSL certificate auto-renewal working
- [ ] Backups completing successfully
- [ ] Monitoring alerts functioning
- [ ] Performance metrics within acceptable ranges
- [ ] Parent notification system operational
- [ ] Child safety filters active

## 📋 Compliance Documentation

### COPPA Compliance Features
1. **Data Minimization**: Only necessary data collected
2. **Parental Consent**: Required before data collection
3. **Data Security**: Encryption at rest and in transit
4. **Access Controls**: Strict authentication and authorization
5. **Data Retention**: Automatic deletion after 90 days
6. **Audit Logging**: Complete activity tracking
7. **Incident Response**: Immediate parent notification procedures

### Security Certifications
- OWASP compliance
- SSL/TLS best practices
- Child safety content filtering
- Regular security updates and patches

---

## 🆘 Emergency Contacts

**Development Team**: dev-team@aiteddybear.com
**Security Team**: security@aiteddybear.com
**COPPA Compliance Officer**: compliance@aiteddybear.com
**System Administrator**: admin@aiteddybear.com

---

**📝 Last Updated**: [Current Date]
**🔖 Version**: 1.0.0
**👥 Maintained by**: AI Teddy Bear DevOps Team