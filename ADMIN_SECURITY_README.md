# 🔒 AI Teddy Bear - Admin Security System

## Overview

This document describes the comprehensive admin security system implemented for the AI Teddy Bear application. The system provides enterprise-grade security for all administrative endpoints with zero-trust architecture.

## 🚨 Security Requirements Met

✅ **JWT + Certificate-based authentication** (NO network-only protection)  
✅ **Multi-factor authentication** for HIGH/CRITICAL operations  
✅ **Rate limiting** with brute-force protection  
✅ **Comprehensive audit logging** for all operations  
✅ **Resource abuse monitoring** and limits  
✅ **COPPA compliance** for child data protection  

## 🔧 Quick Start

### 1. Import Security Components

```python
from src.infrastructure.security.admin_security import (
    require_admin_permission,
    AdminPermission,
    SecurityLevel,
    AdminSession
)
```

### 2. Secure an Admin Endpoint

```python
@app.get("/admin/my-endpoint")
async def my_admin_endpoint(
    session: AdminSession = Depends(
        require_admin_permission(AdminPermission.SYSTEM_ADMIN, SecurityLevel.MEDIUM)
    )
):
    return {"message": "Secured endpoint", "user": session.user_id}
```

### 3. Test the Security

```bash
# Run the security test suite
python test_admin_security.py
```

## 🔐 Security Levels

| Level | Requirements | Use Cases |
|-------|-------------|-----------|
| **LOW** | JWT auth | Basic read operations |
| **MEDIUM** | JWT auth + rate limiting | Standard admin operations |
| **HIGH** | JWT auth + MFA + enhanced logging | Sensitive operations |
| **CRITICAL** | JWT auth + MFA + certificate + approval | System-critical operations |

## 👥 Admin Permissions

| Permission | Description | Typical Users |
|------------|-------------|---------------|
| `SUPER_ADMIN` | Full system access | System owners |
| `SYSTEM_ADMIN` | System operations | Senior admins |
| `SECURITY_ADMIN` | Security management | Security team |
| `STORAGE_ADMIN` | Storage management | Storage specialists |
| `MONITORING_ADMIN` | Monitoring access | DevOps team |
| `ROUTE_ADMIN` | Route management | API team |
| `AUDIT_ADMIN` | Audit log access | Compliance team |
| `READ_ONLY_ADMIN` | View-only access | Junior admins |

## 🔑 Authentication Headers

### Basic Admin Access
```http
Authorization: Bearer <jwt_token>
```

### High Security Operations
```http
Authorization: Bearer <jwt_token>
X-MFA-Token: 123456
```

### Critical Operations
```http
Authorization: Bearer <jwt_token>
X-MFA-Token: 123456
X-Client-Cert: <certificate_data>
X-Client-Cert-Verified: SUCCESS
```

## 📊 Monitoring & Alerts

### Available Metrics
- Active admin sessions
- Failed authentication attempts
- Locked accounts and IPs
- Security events (24h)
- Resource abuse incidents

### Alert Conditions
- Multiple failed login attempts
- Unusual admin activity patterns
- Resource limit violations
- Security policy violations

## 🧪 Testing

### Run Security Tests
```bash
python test_admin_security.py
```

### Expected Output
```
🔒 ADMIN SECURITY TEST REPORT
==================================================
📊 Tests Run: 8
✅ Tests Passed: 8
❌ Tests Failed: 0
📈 Success Rate: 100.0%

✅ NO SECURITY VIOLATIONS FOUND

🟢 SECURITY STATUS: SECURE
✅ All admin endpoints are properly protected
```

## 📁 File Structure

```
src/infrastructure/security/
├── admin_security.py                    # Core security manager
├── admin_endpoints_security_update.py   # Security updater
└── secure_all_admin_endpoints.py        # Comprehensive implementation

test_admin_security.py                   # Security test suite
ADMIN_SECURITY_IMPLEMENTATION_REPORT.md  # Detailed report
ADMIN_SECURITY_README.md                 # This file
```

## 🚀 Implementation Examples

### Decorator Pattern
```python
from src.infrastructure.security.admin_security import admin_endpoint

@admin_endpoint(AdminPermission.STORAGE_ADMIN, SecurityLevel.HIGH)
async def storage_operation(request: Request, session: AdminSession):
    # Automatically secured with comprehensive logging
    return {"status": "success", "user": session.user_id}
```

### Dependency Injection Pattern
```python
@app.post("/admin/critical-action")
async def critical_action(
    session: AdminSession = Depends(
        require_admin_permission(AdminPermission.SUPER_ADMIN, SecurityLevel.CRITICAL)
    )
):
    # Critical operation with maximum security
    return {"message": "Critical action completed"}
```

### Manual Security Check
```python
@app.get("/admin/custom-endpoint")
async def custom_endpoint(request: Request):
    # Manual security implementation
    manager = get_admin_security_manager()
    
    # Extract credentials
    auth_header = request.headers.get("authorization")
    if not auth_header:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    token = auth_header.split(" ")[1]
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    
    # Authenticate
    session = await manager.authenticate_admin(
        request, credentials, AdminPermission.SYSTEM_ADMIN, SecurityLevel.HIGH
    )
    
    return {"message": "Custom secured endpoint", "user": session.user_id}
```

## 🔧 Configuration

### Environment Variables
```bash
# JWT Configuration
JWT_SECRET_KEY=your_secret_key_here
JWT_ALGORITHM=HS256
JWT_EXPIRATION_HOURS=1

# Security Configuration
ADMIN_MFA_REQUIRED=true
ADMIN_CERTIFICATE_AUTH=true
ADMIN_SESSION_TIMEOUT_MINUTES=60
ADMIN_MAX_FAILED_ATTEMPTS=3
ADMIN_LOCKOUT_DURATION_MINUTES=30

# Rate Limiting
ADMIN_RATE_LIMIT_PER_MINUTE=30
ADMIN_BRUTE_FORCE_PROTECTION=true

# Audit Logging
ADMIN_AUDIT_ALL_OPERATIONS=true
ADMIN_RESOURCE_MONITORING=true
```

### Security Manager Configuration
```python
from src.infrastructure.security.admin_security import AdminSecurityConfig

config = AdminSecurityConfig(
    require_mfa=True,
    max_failed_attempts=3,
    lockout_duration_minutes=30,
    session_timeout_minutes=60,
    require_certificate_auth=True,
    audit_all_operations=True,
    rate_limit_requests_per_minute=30,
    brute_force_protection=True,
    resource_abuse_monitoring=True
)
```

## 🐛 Troubleshooting

### Common Issues

#### 401 Unauthorized
- Check JWT token validity
- Verify token hasn't expired
- Ensure proper Authorization header format

#### 403 Forbidden
- Verify user has required admin permission
- Check if account is locked
- Confirm user role is 'admin'

#### 429 Rate Limited
- Wait for rate limit window to reset
- Check if IP is temporarily locked
- Verify rate limiting configuration

#### MFA Required
- Add X-MFA-Token header for HIGH/CRITICAL operations
- Ensure MFA token is 6 digits
- Check MFA token hasn't expired

### Debug Mode
```python
# Enable debug logging
import logging
logging.getLogger("admin_security").setLevel(logging.DEBUG)
```

## 📞 Support

**Security Issues:** security@aiteddybear.com  
**Documentation:** docs@aiteddybear.com  
**Emergency:** Available 24/7  

## 📝 License

This security system is part of the AI Teddy Bear application and is subject to the same licensing terms.

---

**Last Updated:** January 27, 2025  
**Version:** 1.0.0  
**Security Status:** 🟢 FULLY SECURED