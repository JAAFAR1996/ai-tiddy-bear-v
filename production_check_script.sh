#!/bin/bash

# Production Readiness Check Script
# سكريبت فحص الجاهزية للإنتاج

echo "=== Production Readiness Check Script ==="
echo "=== سكريبت فحص الجاهزية للإنتاج ==="
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration - يجب تعديل هذه القيم
DOMAIN="yourdomain.com"
DB_NAME="production_db"
DB_USER="username"
LOG_PATH="/var/log/application.log"

echo "Domain: $DOMAIN"
echo "Database: $DB_NAME"
echo "Log Path: $LOG_PATH"
echo ""

# Function to print status
print_status() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
    fi
}

print_warning() {
    echo -e "${YELLOW}⚠ WARNING${NC}: $1"
}

echo "=== 1. HTTPS & SSL Check ==="
echo "فحص HTTPS و SSL"

# Check HTTPS redirect
echo "Checking HTTP to HTTPS redirect..."
HTTP_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://$DOMAIN)
if [ "$HTTP_RESPONSE" = "301" ] || [ "$HTTP_RESPONSE" = "302" ]; then
    print_status 0 "HTTP redirects to HTTPS"
else
    print_status 1 "HTTP does not redirect to HTTPS (Response: $HTTP_RESPONSE)"
fi

# Check HSTS header
echo "Checking HSTS header..."
HSTS_HEADER=$(curl -s -I https://$DOMAIN | grep -i "strict-transport-security")
if [ ! -z "$HSTS_HEADER" ]; then
    print_status 0 "HSTS header present"
else
    print_status 1 "HSTS header missing"
fi

# Check SSL certificate
echo "Checking SSL certificate..."
SSL_CHECK=$(openssl s_client -connect $DOMAIN:443 -servername $DOMAIN 2>/dev/null | openssl x509 -noout -dates 2>/dev/null)
if [ $? -eq 0 ]; then
    print_status 0 "SSL certificate valid"
    echo "$SSL_CHECK"
else
    print_status 1 "SSL certificate issues"
fi

echo ""
echo "=== 2. Security Endpoints Check ==="
echo "فحص نقاط الأمان"

# Check for debug endpoints
DEBUG_ENDPOINTS=("/debug" "/test" "/admin/debug" "/api/debug" "/.env" "/config")

for endpoint in "${DEBUG_ENDPOINTS[@]}"; do
    echo "Checking $endpoint..."
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN$endpoint)
    if [ "$RESPONSE" = "404" ] || [ "$RESPONSE" = "403" ]; then
        print_status 0 "$endpoint returns $RESPONSE (secure)"
    else
        print_status 1 "$endpoint returns $RESPONSE (potentially insecure)"
    fi
done

echo ""
echo "=== 3. Database Check ==="
echo "فحص قاعدة البيانات"

# Check for test data (requires database access)
if command -v psql &> /dev/null; then
    echo "Checking for test data in database..."
    
    # Check users table for test data
    TEST_USERS=$(psql -d $DB_NAME -t -c "SELECT COUNT(*) FROM users WHERE email LIKE '%test%' OR email LIKE '%mock%';" 2>/dev/null)
    if [ $? -eq 0 ]; then
        if [ "$TEST_USERS" -eq 0 ]; then
            print_status 0 "No test users found"
        else
            print_status 1 "Found $TEST_USERS test users"
        fi
    else
        print_warning "Could not connect to database"
    fi
else
    print_warning "psql not available - skipping database checks"
fi

echo ""
echo "=== 4. File System Check ==="
echo "فحص نظام الملفات"

# Check for test files
echo "Checking for test files..."
if [ -d "./uploads" ]; then
    TEST_FILES=$(find ./uploads -name "*test*" -o -name "*sample*" -o -name "*mock*" 2>/dev/null | wc -l)
    if [ "$TEST_FILES" -eq 0 ]; then
        print_status 0 "No test files found in uploads"
    else
        print_status 1 "Found $TEST_FILES test files in uploads"
    fi
else
    print_warning "uploads directory not found"
fi

# Check for sensitive files
echo "Checking for sensitive files..."
SENSITIVE_FILES=$(find . -name "*.key" -o -name "*.pem" -o -name "*.p12" 2>/dev/null | wc -l)
if [ "$SENSITIVE_FILES" -eq 0 ]; then
    print_status 0 "No sensitive files found in current directory"
else
    print_warning "Found $SENSITIVE_FILES sensitive files - review manually"
fi

echo ""
echo "=== 5. Log Check ==="
echo "فحص السجلات"

if [ -f "$LOG_PATH" ]; then
    echo "Checking recent errors in logs..."
    RECENT_ERRORS=$(tail -n 1000 $LOG_PATH | grep -E "(ERROR|FATAL|CRITICAL)" | wc -l)
    if [ "$RECENT_ERRORS" -eq 0 ]; then
        print_status 0 "No recent errors in logs"
    else
        print_warning "Found $RECENT_ERRORS recent errors in logs"
    fi
    
    # Check log file size
    LOG_SIZE=$(du -h $LOG_PATH | cut -f1)
    echo "Log file size: $LOG_SIZE"
else
    print_warning "Log file not found at $LOG_PATH"
fi

echo ""
echo "=== 6. Performance Check ==="
echo "فحص الأداء"

# Check disk space
echo "Checking disk space..."
DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
if [ "$DISK_USAGE" -lt 80 ]; then
    print_status 0 "Disk usage: ${DISK_USAGE}%"
else
    print_status 1 "Disk usage high: ${DISK_USAGE}%"
fi

# Check memory usage
echo "Checking memory usage..."
if command -v free &> /dev/null; then
    MEMORY_USAGE=$(free | grep Mem | awk '{printf("%.0f", $3/$2 * 100.0)}')
    if [ "$MEMORY_USAGE" -lt 80 ]; then
        print_status 0 "Memory usage: ${MEMORY_USAGE}%"
    else
        print_warning "Memory usage high: ${MEMORY_USAGE}%"
    fi
else
    print_warning "free command not available"
fi

echo ""
echo "=== 7. Health Check ==="
echo "فحص الصحة"

# Check health endpoint
echo "Checking health endpoint..."
HEALTH_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://$DOMAIN/health)
if [ "$HEALTH_RESPONSE" = "200" ]; then
    print_status 0 "Health endpoint responding"
    # Get health details
    curl -s https://$DOMAIN/health | head -10
else
    print_status 1 "Health endpoint not responding (Response: $HEALTH_RESPONSE)"
fi

echo ""
echo "=== 8. Dependencies Check ==="
echo "فحص الاعتماديات"

# Check for package managers and run security audits
if command -v npm &> /dev/null; then
    echo "Running npm audit..."
    npm audit --audit-level=high
    if [ $? -eq 0 ]; then
        print_status 0 "npm audit passed"
    else
        print_status 1 "npm audit found issues"
    fi
fi

if command -v pip &> /dev/null; then
    echo "Checking Python packages..."
    if command -v safety &> /dev/null; then
        safety check
        if [ $? -eq 0 ]; then
            print_status 0 "Python safety check passed"
        else
            print_status 1 "Python safety check found issues"
        fi
    else
        print_warning "safety not installed - run: pip install safety"
    fi
fi

echo ""
echo "=== Summary ==="
echo "الملخص"
echo ""
echo "Manual checks still required:"
echo "الفحوصات اليدوية المطلوبة:"
echo "- Database schema comparison"
echo "- Backup and restore test"
echo "- Load testing (500+ concurrent connections)"
echo "- Authentication flow testing"
echo "- Penetration testing"
echo "- Legal compliance review"
echo ""
echo "Review the checklist file: production_readiness_checklist.md"
echo "راجع ملف القائمة: production_readiness_checklist.md"
echo ""
echo "=== Check Complete ==="
echo "=== انتهى الفحص ==="