# AI Teddy Bear API Error Codes Reference

## 🚨 Error Response Format

All API errors follow a standardized format for consistency and debugging:

```json
{
    "error": {
        "code": "VALIDATION_ERROR",
        "message": "The provided age must be between 2 and 13 for COPPA compliance",
        "field": "age",
        "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2025-07-27T10:30:00Z",
        "documentation_url": "https://docs.aiteddybear.com/errors/VALIDATION_ERROR"
    }
}
```

## 🔢 HTTP Status Codes

| Status | Description | Usage |
|--------|-------------|-------|
| 200 | OK | Successful request |
| 201 | Created | Resource created successfully |
| 400 | Bad Request | Invalid request parameters |
| 401 | Unauthorized | Authentication required |
| 403 | Forbidden | Insufficient permissions |
| 404 | Not Found | Resource not found |
| 409 | Conflict | Resource conflict |
| 422 | Unprocessable Entity | Validation failed |
| 429 | Too Many Requests | Rate limit exceeded |
| 500 | Internal Server Error | Server error |
| 503 | Service Unavailable | Service temporarily down |

## 🔐 Authentication Errors (4xx)

### AUTH_001: Invalid Credentials

```json
{
    "error": {
        "code": "AUTH_001",
        "message": "Invalid email or password",
        "correlation_id": "auth_123456"
    }
}
```

**Cause**: Incorrect login credentials  
**Resolution**: Verify email and password  
**HTTP Status**: 401

### AUTH_002: Token Expired

```json
{
    "error": {
        "code": "AUTH_002",
        "message": "Access token has expired",
        "correlation_id": "auth_234567",
        "expires_at": "2025-07-27T09:30:00Z"
    }
}
```

**Cause**: JWT token past expiration time  
**Resolution**: Refresh token or re-authenticate  
**HTTP Status**: 401

### AUTH_003: Invalid Token Format

```json
{
    "error": {
        "code": "AUTH_003",
        "message": "Malformed JWT token",
        "correlation_id": "auth_345678"
    }
}
```

**Cause**: Corrupted or invalid JWT format  
**Resolution**: Re-authenticate to get new token  
**HTTP Status**: 401

### AUTH_004: Insufficient Permissions

```json
{
    "error": {
        "code": "AUTH_004",
        "message": "Parent access required for this operation",
        "correlation_id": "auth_456789",
        "required_role": "parent"
    }
}
```

**Cause**: User lacks required permissions  
**Resolution**: Contact parent or admin for access  
**HTTP Status**: 403

### AUTH_005: Account Suspended

```json
{
    "error": {
        "code": "AUTH_005",
        "message": "Account suspended due to safety violations",
        "correlation_id": "auth_567890",
        "suspension_reason": "multiple_safety_violations",
        "appeal_url": "https://aiteddybear.com/appeal"
    }
}
```

**Cause**: Account suspended for policy violations  
**Resolution**: Contact support or appeal suspension  
**HTTP Status**: 403

## 👶 Child Safety Errors (4xx)

### SAFETY_001: Age Verification Failed

```json
{
    "error": {
        "code": "SAFETY_001",
        "message": "Child age must be between 2 and 13 for COPPA compliance",
        "correlation_id": "safety_123456",
        "field": "age",
        "provided_value": 15,
        "valid_range": "2-13"
    }
}
```

**Cause**: Child age outside COPPA-compliant range  
**Resolution**: Verify correct age or contact support  
**HTTP Status**: 422

### SAFETY_002: Parental Consent Required

```json
{
    "error": {
        "code": "SAFETY_002",
        "message": "Parental consent required for this feature",
        "correlation_id": "safety_234567",
        "child_id": "child_uuid",
        "feature": "voice_interaction",
        "consent_url": "https://aiteddybear.com/consent/voice_interaction"
    }
}
```

**Cause**: Feature requires explicit parental consent  
**Resolution**: Parent must grant consent first  
**HTTP Status**: 403

### SAFETY_003: Content Violation

```json
{
    "error": {
        "code": "SAFETY_003",
        "message": "Message content violates child safety guidelines",
        "correlation_id": "safety_345678",
        "violation_type": "inappropriate_language",
        "severity": "medium",
        "content_hash": "sha256:abc123..."
    }
}
```

**Cause**: Message contains inappropriate content  
**Resolution**: Rephrase message with appropriate content  
**HTTP Status**: 400

### SAFETY_004: Usage Limit Exceeded

```json
{
    "error": {
        "code": "SAFETY_004",
        "message": "Daily usage limit exceeded",
        "correlation_id": "safety_456789",
        "child_id": "child_uuid",
        "daily_limit_minutes": 60,
        "used_minutes": 65,
        "reset_time": "2025-07-28T00:00:00Z"
    }
}
```

**Cause**: Child exceeded daily usage limit  
**Resolution**: Wait for reset or parent can adjust limits  
**HTTP Status**: 429

### SAFETY_005: Session Blocked by Parent

```json
{
    "error": {
        "code": "SAFETY_005",
        "message": "Session blocked by parental controls",
        "correlation_id": "safety_567890",
        "child_id": "child_uuid",
        "block_reason": "bedtime_restriction",
        "blocked_until": "2025-07-28T07:00:00Z"
    }
}
```

**Cause**: Parent has blocked access during this time  
**Resolution**: Wait for allowed time or contact parent  
**HTTP Status**: 403

## ✅ Validation Errors (4xx)

### VALIDATION_001: Missing Required Field

```json
{
    "error": {
        "code": "VALIDATION_001",
        "message": "Required field missing",
        "correlation_id": "validation_123456",
        "field": "email",
        "location": "request_body"
    }
}
```

**Cause**: Required field not provided  
**Resolution**: Include the missing field  
**HTTP Status**: 400

### VALIDATION_002: Invalid Field Format

```json
{
    "error": {
        "code": "VALIDATION_002",
        "message": "Invalid email format",
        "correlation_id": "validation_234567",
        "field": "email",
        "provided_value": "invalid-email",
        "expected_format": "email"
    }
}
```

**Cause**: Field value doesn't match expected format  
**Resolution**: Correct the field format  
**HTTP Status**: 400

### VALIDATION_003: Field Value Out of Range

```json
{
    "error": {
        "code": "VALIDATION_003",
        "message": "Age must be between 2 and 13",
        "correlation_id": "validation_345678",
        "field": "age",
        "provided_value": 15,
        "min_value": 2,
        "max_value": 13
    }
}
```

**Cause**: Numeric field outside valid range  
**Resolution**: Provide value within valid range  
**HTTP Status**: 400

### VALIDATION_004: Invalid Enum Value

```json
{
    "error": {
        "code": "VALIDATION_004",
        "message": "Invalid safety level",
        "correlation_id": "validation_456789",
        "field": "safety_level",
        "provided_value": "extreme",
        "valid_values": ["low", "medium", "high"]
    }
}
```

**Cause**: Enum field contains invalid value  
**Resolution**: Use one of the valid enum values  
**HTTP Status**: 400

### VALIDATION_005: String Length Violation

```json
{
    "error": {
        "code": "VALIDATION_005",
        "message": "Child name must be between 1 and 50 characters",
        "correlation_id": "validation_567890",
        "field": "name",
        "provided_length": 75,
        "min_length": 1,
        "max_length": 50
    }
}
```

**Cause**: String field length outside valid range  
**Resolution**: Adjust string length to meet requirements  
**HTTP Status**: 400

## 🚦 Rate Limiting Errors (4xx)

### RATE_001: General Rate Limit Exceeded

```json
{
    "error": {
        "code": "RATE_001",
        "message": "Rate limit exceeded",
        "correlation_id": "rate_123456",
        "limit": 60,
        "window": "60s",
        "retry_after": 45,
        "reset_time": "2025-07-27T10:31:00Z"
    }
}
```

**Cause**: Too many requests in time window  
**Resolution**: Wait for retry_after seconds  
**HTTP Status**: 429

### RATE_002: AI Generation Rate Limit

```json
{
    "error": {
        "code": "RATE_002",
        "message": "AI generation rate limit exceeded",
        "correlation_id": "rate_234567",
        "child_id": "child_uuid",
        "limit": 10,
        "window": "60s",
        "retry_after": 30
    }
}
```

**Cause**: Too many AI generation requests  
**Resolution**: Wait before making more AI requests  
**HTTP Status**: 429

### RATE_003: Audio Processing Rate Limit

```json
{
    "error": {
        "code": "RATE_003",
        "message": "Audio processing rate limit exceeded",
        "correlation_id": "rate_345678",
        "limit": 5,
        "window": "60s",
        "retry_after": 25
    }
}
```

**Cause**: Too many audio processing requests  
**Resolution**: Wait before making more audio requests  
**HTTP Status**: 429

## 🔍 Resource Errors (4xx)

### RESOURCE_001: Not Found

```json
{
    "error": {
        "code": "RESOURCE_001",
        "message": "Child profile not found",
        "correlation_id": "resource_123456",
        "resource_type": "child",
        "resource_id": "child_uuid"
    }
}
```

**Cause**: Requested resource doesn't exist  
**Resolution**: Verify resource ID or create resource  
**HTTP Status**: 404

### RESOURCE_002: Already Exists

```json
{
    "error": {
        "code": "RESOURCE_002",
        "message": "Email address already registered",
        "correlation_id": "resource_234567",
        "resource_type": "parent",
        "field": "email",
        "existing_value": "parent@example.com"
    }
}
```

**Cause**: Resource with same identifier already exists  
**Resolution**: Use different identifier or update existing  
**HTTP Status**: 409

### RESOURCE_003: Access Denied

```json
{
    "error": {
        "code": "RESOURCE_003",
        "message": "Access denied to child profile",
        "correlation_id": "resource_345678",
        "resource_type": "child",
        "resource_id": "child_uuid",
        "reason": "not_parent"
    }
}
```

**Cause**: User doesn't have access to resource  
**Resolution**: Verify ownership or request access  
**HTTP Status**: 403

## ⚙️ Service Errors (5xx)

### SERVICE_001: Internal Server Error

```json
{
    "error": {
        "code": "SERVICE_001",
        "message": "An unexpected error occurred",
        "correlation_id": "service_123456",
        "timestamp": "2025-07-27T10:30:00Z",
        "support_reference": "INC-2025-0727-001"
    }
}
```

**Cause**: Unexpected server error  
**Resolution**: Contact support with correlation ID  
**HTTP Status**: 500

### SERVICE_002: AI Service Unavailable

```json
{
    "error": {
        "code": "SERVICE_002",
        "message": "AI generation service temporarily unavailable",
        "correlation_id": "service_234567",
        "service": "openai_gpt",
        "estimated_recovery": "2025-07-27T10:45:00Z",
        "fallback_available": true
    }
}
```

**Cause**: External AI service is down  
**Resolution**: Retry later or use fallback if available  
**HTTP Status**: 503

### SERVICE_003: Database Connection Error

```json
{
    "error": {
        "code": "SERVICE_003",
        "message": "Database connection failed",
        "correlation_id": "service_345678",
        "service": "postgresql",
        "retry_recommended": true
    }
}
```

**Cause**: Database connectivity issues  
**Resolution**: Retry request or contact support  
**HTTP Status**: 503

### SERVICE_004: External API Error

```json
{
    "error": {
        "code": "SERVICE_004",
        "message": "External service integration failed",
        "correlation_id": "service_456789",
        "external_service": "content_moderation",
        "error_details": "API rate limit exceeded",
        "fallback_used": true
    }
}
```

**Cause**: External service integration failure  
**Resolution**: Automatically handled with fallback  
**HTTP Status**: 202

## 🔧 Configuration Errors (5xx)

### CONFIG_001: Missing Configuration

```json
{
    "error": {
        "code": "CONFIG_001",
        "message": "Required configuration missing",
        "correlation_id": "config_123456",
        "missing_config": "OPENAI_API_KEY",
        "config_type": "environment_variable"
    }
}
```

**Cause**: Required configuration not set  
**Resolution**: Admin must configure missing setting  
**HTTP Status**: 500

### CONFIG_002: Invalid Configuration

```json
{
    "error": {
        "code": "CONFIG_002",
        "message": "Invalid API key configuration",
        "correlation_id": "config_234567",
        "config_key": "OPENAI_API_KEY",
        "validation_error": "Invalid key format"
    }
}
```

**Cause**: Configuration value is invalid  
**Resolution**: Admin must fix configuration  
**HTTP Status**: 500

## 📱 WebSocket Errors

### WS_001: Connection Failed

```json
{
    "type": "error",
    "error": {
        "code": "WS_001",
        "message": "WebSocket connection failed",
        "correlation_id": "ws_123456",
        "reason": "authentication_failed"
    }
}
```

**Cause**: WebSocket connection couldn't be established  
**Resolution**: Check authentication and retry  

### WS_002: Invalid Message Format

```json
{
    "type": "error",
    "error": {
        "code": "WS_002",
        "message": "Invalid message format",
        "correlation_id": "ws_234567",
        "expected_fields": ["type", "content"],
        "missing_fields": ["type"]
    }
}
```

**Cause**: WebSocket message missing required fields  
**Resolution**: Include all required fields in message  

### WS_003: Session Expired

```json
{
    "type": "error",
    "error": {
        "code": "WS_003",
        "message": "WebSocket session expired",
        "correlation_id": "ws_345678",
        "expires_at": "2025-07-27T10:30:00Z"
    }
}
```

**Cause**: WebSocket session past expiration  
**Resolution**: Reconnect with fresh authentication  

## 🛠️ Error Handling Best Practices

### 1. Client-Side Error Handling

```javascript
async function handleApiCall() {
    try {
        const response = await fetch('/api/v1/children', {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(childData)
        });
        
        if (!response.ok) {
            const error = await response.json();
            handleApiError(error);
            return;
        }
        
        const data = await response.json();
        return data;
        
    } catch (error) {
        console.error('Network error:', error);
        throw new Error('Network connection failed');
    }
}

function handleApiError(errorResponse) {
    const { error } = errorResponse;
    
    switch (error.code) {
        case 'AUTH_002':
            // Token expired - refresh and retry
            refreshToken().then(() => retryRequest());
            break;
            
        case 'SAFETY_002':
            // Parental consent required
            showConsentDialog(error.consent_url);
            break;
            
        case 'RATE_001':
            // Rate limited - wait and retry
            setTimeout(retryRequest, error.retry_after * 1000);
            break;
            
        case 'VALIDATION_001':
        case 'VALIDATION_002':
        case 'VALIDATION_003':
            // Validation error - show to user
            showValidationError(error.field, error.message);
            break;
            
        default:
            // Generic error
            showGenericError(error.message, error.correlation_id);
    }
}
```

### 2. Retry Logic

```javascript
async function apiCallWithRetry(apiCall, maxRetries = 3) {
    for (let attempt = 1; attempt <= maxRetries; attempt++) {
        try {
            return await apiCall();
        } catch (error) {
            if (error.code === 'SERVICE_002' && attempt < maxRetries) {
                // Exponential backoff for service unavailable
                const delay = Math.pow(2, attempt) * 1000;
                await new Promise(resolve => setTimeout(resolve, delay));
                continue;
            }
            throw error;
        }
    }
}
```

### 3. Error Logging

```javascript
function logError(error, context = {}) {
    const logData = {
        timestamp: new Date().toISOString(),
        error_code: error.code,
        correlation_id: error.correlation_id,
        message: error.message,
        context: context,
        user_agent: navigator.userAgent,
        url: window.location.href
    };
    
    // Send to logging service
    fetch('/api/v1/logs/client-errors', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(logData)
    }).catch(err => console.error('Failed to log error:', err));
}
```

## 📞 Support and Debugging

### Getting Help

1. **Check correlation ID**: Every error includes a correlation_id for tracking
2. **Review documentation**: Links provided in error responses
3. **Contact support**: Include correlation_id in support requests
4. **Check status page**: https://status.aiteddybear.com

### Common Solutions

| Error Pattern | Common Cause | Quick Fix |
|---------------|--------------|-----------|
| AUTH_* | Authentication issues | Refresh token or re-login |
| SAFETY_* | Child safety violations | Follow safety guidelines |
| VALIDATION_* | Input validation | Check field requirements |
| RATE_* | Too many requests | Implement rate limiting |
| SERVICE_* | Server issues | Retry with backoff |

### Debug Mode

Enable debug mode for detailed error information:

```javascript
const client = new AITeddyBearClient({
    apiKey: 'your-key',
    debug: true  // Shows detailed error information
});
```

**Note**: Never enable debug mode in production as it may expose sensitive information.
