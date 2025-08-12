# 🧸 AI Teddy Bear - Unified CLI Guide

## Overview

The AI Teddy Bear Unified CLI provides a single, powerful interface for managing all aspects of the AI Teddy Bear project, from development to production deployment.

## Installation & Setup

```bash
# Make CLI executable
chmod +x ai_teddy_cli.py

# Add to PATH (optional)
export PATH="$PATH:$(pwd)"

# Verify installation
python ai_teddy_cli.py --help
```

## Available Commands

### 🔍 System Analysis Commands

#### Complete System Analysis
```bash
python ai_teddy_cli.py check --full
```
Runs comprehensive analysis including:
- Production readiness validation
- Security dependency audit
- Dead code detection
- Test coverage analysis
- ESP32 connectivity verification

#### Connectivity Testing
```bash
python ai_teddy_cli.py check --connectivity
```
Tests ESP32-Server connections:
- Network connectivity
- SSL/TLS security validation
- Authentication flow testing

#### Security Scanning
```bash
python ai_teddy_cli.py check --security
```
Comprehensive security audit:
- Dependency vulnerability scanning
- JWT security validation
- Secrets audit
- Child safety compliance (COPPA)

#### Performance Validation
```bash
python ai_teddy_cli.py check --performance
```
Performance optimization checks:
- Database query optimization
- Memory usage analysis
- ESP32 performance measurements

### 🧪 Testing Commands

#### Run All Tests
```bash
python ai_teddy_cli.py test --all
```
Executes complete test suite:
- Unit tests
- Integration tests
- End-to-end tests
- Security tests

#### Security Tests Only
```bash
python ai_teddy_cli.py test --security
```
Focused security testing:
- JWT penetration tests
- Authentication bypass attempts
- Environment security validation

### 🚀 Deployment Commands

#### Production Deployment
```bash
python ai_teddy_cli.py deploy --production
```
Full production deployment with:
- Pre-deployment validation
- Zero-downtime deployment
- Health check verification
- Automatic rollback on failure

#### Staging Deployment
```bash
python ai_teddy_cli.py deploy --staging
```
Deploy to staging environment for testing.

### 📊 Monitoring Commands

#### Health Monitoring
```bash
python ai_teddy_cli.py monitor --health
```
Real-time system health monitoring:
- Service availability
- Performance metrics
- Child safety alerts
- Database health

#### Live Log Monitoring
```bash
python ai_teddy_cli.py monitor --logs
```
Stream live system logs with filtering.

### 💾 Backup Commands

#### Create Backup
```bash
python ai_teddy_cli.py backup --create
```
Creates comprehensive backup including:
- Database snapshot
- Configuration files
- User data (anonymized)
- System state

#### Restore from Backup
```bash
python ai_teddy_cli.py backup --restore backup_file.tar.gz
```
Restore system from backup file.

## Usage Examples

### Daily Development Workflow
```bash
# Morning health check
python ai_teddy_cli.py check --full

# Run tests before committing
python ai_teddy_cli.py test --all

# Security scan before release
python ai_teddy_cli.py check --security
```

### Production Deployment Workflow
```bash
# Pre-deployment validation
python ai_teddy_cli.py check --full
python ai_teddy_cli.py test --all

# Create backup before deployment
python ai_teddy_cli.py backup --create

# Deploy to production
python ai_teddy_cli.py deploy --production

# Monitor post-deployment
python ai_teddy_cli.py monitor --health
```

### Troubleshooting Workflow
```bash
# Check ESP32 connectivity issues
python ai_teddy_cli.py check --connectivity

# Performance analysis
python ai_teddy_cli.py check --performance

# Security incident response
python ai_teddy_cli.py check --security
python ai_teddy_cli.py test --security
```

## Configuration

The CLI uses `cli_config.json` for configuration. Key sections:

### Script Mapping
- Maps CLI commands to underlying Python scripts
- Defines argument passing
- Sets execution order

### Environment Checks
- Python version validation
- Database connectivity
- Redis availability
- ESP32 device detection

### Security Requirements
- JWT validation settings
- COPPA compliance checks
- Encryption requirements
- Audit logging configuration

## Child Safety Features

The CLI includes special handling for child safety:

- **COPPA Compliance**: Automatic validation of child data protection
- **Content Filtering**: Active monitoring of inappropriate content
- **Parental Controls**: Verification of parental consent systems
- **Session Monitoring**: Real-time child interaction oversight

## Error Handling

The CLI provides detailed error reporting:

```bash
# Example error output
❌ Security scan failed: 3 critical vulnerabilities found
  - CVE-2023-1234 in dependency 'package-name'
  - Exposed JWT secret in configuration
  - Missing COPPA consent validation

🔧 Recommended actions:
  1. Update vulnerable dependencies
  2. Rotate JWT secrets
  3. Implement consent validation
```

## Integration with CI/CD

### GitHub Actions
```yaml
- name: Run AI Teddy CLI Tests
  run: |
    python ai_teddy_cli.py check --full
    python ai_teddy_cli.py test --all
```

### Docker Integration
```dockerfile
# Add CLI to Docker image
COPY ai_teddy_cli.py /app/
RUN chmod +x /app/ai_teddy_cli.py

# Health check using CLI
HEALTHCHECK CMD python /app/ai_teddy_cli.py monitor --health
```

## Advanced Usage

### Custom Script Integration
```python
# Add custom scripts to cli_config.json
{
  "commands": {
    "custom": {
      "subcommands": {
        "my_check": {
          "scripts": ["custom/my_check.py"],
          "description": "Custom validation script"
        }
      }
    }
  }
}
```

### Parallel Execution
```bash
# Run multiple checks in parallel (future feature)
python ai_teddy_cli.py check --full --parallel
```

## Troubleshooting

### Common Issues

1. **Script Not Found**
   ```bash
   ❌ Script not found: scripts/missing_script.py
   ```
   - Check if script exists
   - Verify cli_config.json mapping

2. **Permission Denied**
   ```bash
   chmod +x ai_teddy_cli.py
   chmod +x scripts/*.py
   ```

3. **Import Errors**
   ```bash
   # Ensure Python path is correct
   export PYTHONPATH="$(pwd):$PYTHONPATH"
   ```

### Debug Mode
```bash
# Run with verbose output (future feature)
python ai_teddy_cli.py check --full --debug
```

## Security Considerations

- **Credential Management**: CLI never stores or logs sensitive credentials
- **Audit Trail**: All CLI operations are logged for security auditing
- **Child Data Protection**: Special handling for COPPA-protected data
- **Access Control**: Role-based command access (future feature)

## Support

For issues or questions:
- Check the troubleshooting section
- Review error messages and suggested actions
- Consult individual script documentation in `/scripts/` directory

---

**Version**: 5.0.0  
**Last Updated**: 2025-08-12  
**Compatibility**: Python 3.10+, PostgreSQL, Redis, ESP32