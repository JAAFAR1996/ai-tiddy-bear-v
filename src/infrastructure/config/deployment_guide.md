# Configuration Management Deployment Guide

## Overview

This guide covers the complete deployment of the AI Teddy Bear configuration management system across different environments and platforms.

## 🚀 Quick Start

### 1. Environment Configuration Files

The system supports multiple environments with dedicated configuration files:

- `config/development.yaml` - Local development
- `config/staging.yaml` - Pre-production staging
- `config/production.yaml` - Production environment
- `config/test.yaml` - Automated testing

### 2. Configuration Sources Priority

The system loads configuration from multiple sources in this priority order:

1. **Environment Variables** (highest priority)
2. **Docker Secrets** (Docker Swarm/Compose)
3. **Kubernetes Secrets** (Kubernetes deployments)
4. **HashiCorp Vault** (if configured)
5. **AWS Secrets Manager** (if configured)
6. **Configuration Files** (YAML files)
7. **Default Values** (lowest priority)

## 🐳 Docker Deployment

### Docker Compose with Configuration Management

1. **Setup Docker Secrets**:
   ```bash
   ./scripts/setup-docker-secrets.sh
   ```

2. **Deploy with Docker Compose**:
   ```bash
   docker-compose -f docker-compose.config.yml up -d
   ```

3. **Verify Configuration**:
   ```bash
   curl http://localhost:8000/api/config/health
   ```

### Docker Secrets Management

The system automatically detects and uses Docker Secrets:

```yaml
# docker-compose.yml
services:
  ai-teddy-bear:
    secrets:
      - database_url
      - jwt_secret_key
      - openai_api_key
    environment:
      ENABLE_DOCKER_SECRETS: "true"
      DOCKER_SECRETS_PATH: /run/secrets
```

## ☸️ Kubernetes Deployment

### Complete Kubernetes Setup

1. **Deploy to Kubernetes**:
   ```bash
   ./scripts/deploy-kubernetes-config.sh
   ```

2. **Verify Deployment**:
   ```bash
   kubectl get all -n ai-teddy-bear
   kubectl logs -n ai-teddy-bear -l app=ai-teddy-bear -f
   ```

3. **Test Configuration API**:
   ```bash
   kubectl port-forward -n ai-teddy-bear service/ai-teddy-bear-service 8080:80
   curl http://localhost:8080/api/config/health
   ```

### Kubernetes Configuration Structure

```yaml
# ConfigMap for non-sensitive configuration
apiVersion: v1
kind: ConfigMap
metadata:
  name: ai-teddy-bear-config
data:
  LOG_LEVEL: "INFO"
  ENVIRONMENT: "production"

# Secret for sensitive configuration
apiVersion: v1
kind: Secret
metadata:
  name: ai-teddy-bear-secrets
stringData:
  DATABASE_URL: "postgresql://..."
  JWT_SECRET_KEY: "..."
```

## 🔐 HashiCorp Vault Integration

### Vault Setup

1. **Configure Vault**:
   ```bash
   export VAULT_ADDR="https://vault.company.com"
   export VAULT_TOKEN="your-vault-token"
   ```

2. **Store Secrets in Vault**:
   ```bash
   vault kv put secret/ai-teddy-bear/production \
     DATABASE_URL="postgresql://..." \
     JWT_SECRET_KEY="..." \
     OPENAI_API_KEY="sk-..."
   ```

3. **Application Configuration**:
   ```yaml
   # Environment variables
   VAULT_URL: "https://vault.company.com"
   VAULT_TOKEN: "your-vault-token"
   VAULT_PATH: "secret/ai-teddy-bear"
   ```

## ☁️ AWS Secrets Manager

### AWS Secrets Integration

1. **Create Secrets in AWS**:
   ```bash
   aws secretsmanager create-secret \
     --name "ai-teddy-bear/production" \
     --description "AI Teddy Bear production secrets" \
     --secret-string '{"DATABASE_URL":"postgresql://...","JWT_SECRET_KEY":"..."}'
   ```

2. **Configure Application**:
   ```yaml
   # Environment variables
   AWS_REGION: "us-east-1"
   AWS_ACCESS_KEY_ID: "your-access-key"
   AWS_SECRET_ACCESS_KEY: "your-secret-key"
   ```

## 🔧 Configuration API

### Configuration Management Endpoints

The system provides a comprehensive REST API for configuration management:

```bash
# Health check
GET /api/config/health

# Get all configuration
GET /api/config

# Get specific configuration item
GET /api/config/{key}

# Update configuration item
POST /api/config/{key}

# Bulk update configuration
POST /api/config/bulk-update

# Validate configuration
POST /api/config/validate

# Get configuration schema
GET /api/config/schema

# Reload configuration
POST /api/config/reload
```

### Example API Usage

```bash
# Check configuration health
curl http://localhost:8000/api/config/health

# Get all configuration (non-sensitive)
curl http://localhost:8000/api/config

# Get specific configuration item
curl http://localhost:8000/api/config/LOG_LEVEL

# Update configuration item
curl -X POST http://localhost:8000/api/config/LOG_LEVEL \
  -H "Content-Type: application/json" \
  -d '{"key":"LOG_LEVEL","value":"DEBUG","source":"env"}'

# Validate configuration data
curl -X POST http://localhost:8000/api/config/validate \
  -H "Content-Type: application/json" \
  -d '{"config_data":{"LOG_LEVEL":"DEBUG","PORT":8000}}'
```

## 🏗️ Application Integration

### FastAPI Integration

```python
from fastapi import FastAPI
from src.infrastructure.config import (
    setup_config_integration, config_lifespan, 
    add_config_routes, get_config_manager
)

# Create FastAPI app with configuration lifespan
app = FastAPI(lifespan=config_lifespan)

# Add configuration routes
add_config_routes(app)

# Use configuration in your application
@app.get("/")
async def root(config_manager = Depends(get_config_manager)):
    app_name = config_manager.get("APP_NAME", "AI Teddy Bear")
    return {"message": f"Welcome to {app_name}"}
```

### Dependency Injection

```python
from src.infrastructure.config import get_config_manager, with_config

# Using dependency injection
@app.get("/info")
async def get_info(config_manager = Depends(get_config_manager)):
    return {
        "app_name": config_manager.get("APP_NAME"),
        "version": config_manager.get("APP_VERSION"),
        "environment": config_manager.environment.value
    }

# Using decorator
@with_config("DATABASE_POOL_SIZE", 10)
def setup_database(config_database_pool_size):
    print(f"Setting up database with pool size: {config_database_pool_size}")
```

## 📊 Monitoring and Health Checks

### Container Health Checks

For Docker and Kubernetes deployments, the system provides specialized health checks:

```python
from src.infrastructure.config.docker_integration import (
    add_container_routes, container_config_manager
)

# Add container-specific routes
add_container_routes(app)

# Available endpoints:
# GET /health - Liveness probe
# GET /ready - Readiness probe  
# GET /container-info - Container metadata
```

### Configuration Validation

The system continuously validates configuration:

```python
# Get validation status
validation_result = await config_manager.validate_container_deployment()

if not validation_result["valid"]:
    print("Configuration errors:", validation_result["errors"])
```

## 🔄 Hot Configuration Reload

### Dynamic Configuration Updates

The system supports hot reloading of configuration without restart:

```python
# Add configuration watcher
config_manager.add_watcher(my_config_change_handler)

# Configuration changes trigger callbacks
async def my_config_change_handler(key: str, value: Any):
    print(f"Configuration changed: {key} = {value}")
    # Reload dependent services
```

### Background Refresh

Configuration is automatically refreshed from sources:

- **Interval**: Every 5 minutes
- **Cache TTL**: 5 minutes
- **Sources**: Vault, AWS Secrets Manager, Config Files

## 🛠️ Development Setup

### Local Development

1. **Copy development configuration**:
   ```bash
   cp config/development.yaml config/local.yaml
   # Edit config/local.yaml with your local settings
   ```

2. **Set environment**:
   ```bash
   export ENVIRONMENT=development
   export LOG_LEVEL=DEBUG
   ```

3. **Run application**:
   ```bash
   python -m uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
   ```

### Configuration Examples

```python
# examples/config_usage.py
from src.infrastructure.config import config_manager

# Basic usage
database_url = config_manager.get("DATABASE_URL")
pool_size = config_manager.get_int("DATABASE_POOL_SIZE", 10)
debug_mode = config_manager.get_bool("DEBUG", False)

# Typed getters
max_connections = config_manager.get_int("REDIS_MAX_CONNECTIONS", 100)
timeout = config_manager.get_float("REQUEST_TIMEOUT", 30.0)
allowed_hosts = config_manager.get_list("ALLOWED_HOSTS", ",", ["localhost"])

# Environment-specific logic
if config_manager.environment == Environment.PRODUCTION:
    # Production-specific configuration
    ssl_required = True
else:
    # Development configuration
    ssl_required = False
```

## 🔐 Security Best Practices

### Secret Management

1. **Never commit secrets to version control**
2. **Use environment variables or secret management systems**
3. **Encrypt sensitive configuration values**
4. **Implement proper access controls**
5. **Audit configuration changes**

### Access Control

```python
# Role-based configuration access
@app.get("/api/config/sensitive")
@require_role("admin")
async def get_sensitive_config():
    return config_manager.get_all_config(include_sensitive=True)
```

### Audit Logging

All configuration changes are automatically logged:

```python
# Configuration changes are logged with:
# - User/system making the change
# - Timestamp
# - Configuration key (sensitive keys are masked)
# - Source of the change
# - Environment context
```

## 🚨 Troubleshooting

### Common Issues

1. **Configuration not loading**:
   ```bash
   # Check configuration sources
   curl http://localhost:8000/api/config/health
   
   # Check application logs
   docker logs ai-teddy-bear-app
   kubectl logs -n ai-teddy-bear -l app=ai-teddy-bear
   ```

2. **Secret access issues**:
   ```bash
   # Docker Secrets
   docker secret ls
   docker exec ai-teddy-bear-app ls -la /run/secrets/
   
   # Kubernetes Secrets
   kubectl get secrets -n ai-teddy-bear
   kubectl describe secret ai-teddy-bear-secrets -n ai-teddy-bear
   ```

3. **Vault connectivity**:
   ```bash
   # Test Vault connection
   vault status
   vault kv get secret/ai-teddy-bear/production
   ```

4. **AWS Secrets Manager**:
   ```bash
   # Test AWS connectivity
   aws secretsmanager list-secrets
   aws secretsmanager get-secret-value --secret-id ai-teddy-bear/production
   ```

### Debug Mode

Enable debug logging for configuration:

```bash
export LOG_LEVEL=DEBUG
export CONFIG_DEBUG=true
```

This will provide detailed logging of:
- Configuration source attempts
- Secret loading processes
- Validation results
- Cache operations

## 📋 Deployment Checklist

### Pre-deployment

- [ ] Configuration files reviewed and updated
- [ ] Secrets created in appropriate system (Vault/AWS/K8s/Docker)
- [ ] Environment variables configured
- [ ] Database connections tested
- [ ] External service credentials validated

### Deployment

- [ ] Application deployed successfully
- [ ] Health checks passing
- [ ] Configuration API responding
- [ ] All required secrets loaded
- [ ] Logging working correctly

### Post-deployment

- [ ] Monitoring configured
- [ ] Alerts set up for configuration issues
- [ ] Backup procedures in place
- [ ] Documentation updated
- [ ] Team notified of deployment

## 📚 Additional Resources

- [Configuration Schema Reference](../config/README.md)
- [Docker Integration Guide](./docker_integration.py)
- [Kubernetes Examples](../../kubernetes/)
- [API Documentation](./config_integration.py)
- [Security Guidelines](../security/README.md)