#!/bin/bash

echo "🏭 AI Teddy Bear ESP32 - Production Preparation Script (FIXED)"
echo "============================================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if we're in the right directory
if [ ! -f "platformio.ini" ]; then
    print_error "platformio.ini not found. Please run this script from the project root directory."
    exit 1
fi

print_status "Starting production cleanup..."

# 1. Remove development files and directories
print_status "Removing development files..."

# Remove example files
if [ -d "examples" ]; then
    rm -rf examples/
    print_success "Removed examples/ directory"
fi

# Remove logs
if [ -d "logs" ]; then
    rm -rf logs/
    print_success "Removed logs/ directory"
fi

# Remove development documentation
if [ -d "docs/analysis/مهمة" ]; then
    rm -rf "docs/analysis/مهمة/"
    print_success "Removed development documentation"
fi

# Remove integration examples
if [ -f "audio_enhancement_integration_examples.cpp" ]; then
    rm audio_enhancement_integration_examples.cpp
    print_success "Removed audio integration examples"
fi

if [ -f "monitoring_integration_examples.cpp" ]; then
    rm monitoring_integration_examples.cpp
    print_success "Removed monitoring integration examples"
fi

# 2. Optional: Move test directory (instead of deleting)
if [ -d "test" ]; then
    read -p "Do you want to remove the test/ directory? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf test/
        print_success "Removed test/ directory"
    else
        print_warning "Keeping test/ directory (recommended for CI/CD)"
    fi
fi

# 3. Clean build artifacts ONLY - NO BUILD COMMANDS
print_status "Cleaning build artifacts..."

# Remove .pio directory if it exists
if [ -d ".pio" ]; then
    rm -rf .pio/
    print_success "Removed .pio build directory"
fi

# Clean any remaining build files
if [ -d ".pioenvs" ]; then
    rm -rf .pioenvs/
    print_success "Removed .pioenvs directory"
fi

if [ -d ".piolibdeps" ]; then
    rm -rf .piolibdeps/
    print_success "Removed .piolibdeps directory"
fi

# 4. Backup original platformio.ini
print_status "Backing up platformio.ini..."
cp platformio.ini platformio.ini.backup
print_success "Created platformio.ini.backup"

# 5. Update platformio.ini for production - FIXED ARCHITECTURE
print_status "Updating platformio.ini for production..."

# Create clean production platformio.ini with PINNED VERSIONS
cat > platformio.ini << 'EOF'
; PlatformIO Project Configuration File - PRODUCTION CLEAN (FIXED)
;
; AI Teddy Bear ESP32 - Production Ready Configuration
; ARCHITECTURAL FIXES:
; - Pinned library versions (no ranges)
; - LDF mode set to 'chain' (not chain+)
; - Consistent platform versions
; - Removed problematic dependency combinations
;

[env:esp32dev]
upload_port = COM5
platform = espressif32@6.4.0
board = esp32dev
framework = arduino
upload_protocol = esptool
monitor_speed = 115200

; PINNED LIBRARY VERSIONS - No ranges to avoid dependency resolution conflicts
lib_deps = 
	fastled/FastLED@3.6.0
	bblanchon/ArduinoJson@6.21.4
	Links2004/WebSockets@2.4.1
	densaugeo/base64@1.4.0
	ayushsharma82/ElegantOTA@2.2.9
	arduino-libraries/NTPClient@3.2.1
	bblanchon/StreamUtils@1.7.3

; CONSERVATIVE LDF MODE - Prevents exponential dependency resolution
lib_ldf_mode = chain

build_flags = 
	-DCORE_DEBUG_LEVEL=1
	-Os
	-DARDUINO_RUNNING_CORE=1
	-DARDUINO_EVENT_RUNNING_CORE=1
	-DDISABLE_ALL_LIBRARY_WARNINGS
	-DCONFIG_BT_ENABLED=1
	-DCONFIG_BLUEDROID_ENABLED=1
	-DCONFIG_BT_BLE_ENABLED=1
	-DCONFIG_BT_GATTS_ENABLE=1
	-DCONFIG_MBEDTLS_GCM_C=1
	-DCONFIG_MBEDTLS_AES_C=1
	-DBLE_PROVISIONING_ENABLED=1

monitor_filters = esp32_exception_decoder
upload_speed = 921600

; Production Release Environment - Optimized for deployment
[env:esp32dev-release]
extends = env:esp32dev
build_type = release

build_flags = 
	-DPRODUCTION_BUILD=1
	-DNDEBUG
	-DCORE_DEBUG_LEVEL=0
	-Os
	-ffunction-sections
	-fdata-sections
	-Wl,--gc-sections
	-Wl,--strip-debug
	-DARDUINO_RUNNING_CORE=1
	-DARDUINO_EVENT_RUNNING_CORE=1
	-DDISABLE_ALL_LIBRARY_WARNINGS
	-DCONFIG_BT_ENABLED=1
	-DCONFIG_BLUEDROID_ENABLED=1
	-DCONFIG_BT_BLE_ENABLED=1
	-DCONFIG_BT_GATTS_ENABLE=1
	-DCONFIG_MBEDTLS_GCM_C=1
	-DCONFIG_MBEDTLS_AES_C=1
	-DBLE_PROVISIONING_ENABLED=1
	-DJWT_MANAGER_ENABLED=1
	-DUSE_SSL=1

board_build.partitions = huge_app.csv

; ESP32-S3 Production Environment - CONSISTENT PLATFORM VERSION
[env:esp32s3dev]
platform = espressif32@6.4.0
board = esp32-s3-devkitc-1
framework = arduino
upload_port = COM5
monitor_speed = 115200
upload_speed = 921600

lib_deps = 
	${env:esp32dev.lib_deps}

lib_ldf_mode = chain

build_flags = 
	-DPRODUCTION_BUILD=1
	-DCORE_DEBUG_LEVEL=0
	-Os
	-DARDUINO_RUNNING_CORE=1
	-DARDUINO_EVENT_RUNNING_CORE=1
	-DDISABLE_ALL_LIBRARY_WARNINGS
	-DCONFIG_BT_ENABLED=1
	-DCONFIG_BLUEDROID_ENABLED=1
	-DCONFIG_BT_BLE_ENABLED=1
	-DCONFIG_BT_GATTS_ENABLE=1
	-DCONFIG_BT_BLE_42_FEATURES_SUPPORTED=1
	-DCONFIG_BT_BLE_50_FEATURES_SUPPORTED=1
	-DCONFIG_MBEDTLS_GCM_C=1
	-DCONFIG_MBEDTLS_AES_C=1
	-DBLE_PROVISIONING_ENABLED=1
	-DJWT_MANAGER_ENABLED=1
	-DJWT_ENABLE_STATISTICS=1
	-DESP32S3=1
	-DCONFIG_ESP32S3_SPIRAM_SUPPORT=1
	-DUSE_SSL=1

board_build.partitions = huge_app.csv
monitor_filters = esp32_exception_decoder
EOF

print_success "Updated platformio.ini for production (FIXED ARCHITECTURE)"

# 6. Security check for config.h
print_status "Checking security configurations..."

if [ -f "include/config.h" ]; then
    if grep -q "your-device-secret-key-32-chars" include/config.h; then
        print_error "Default secret key found in config.h!"
        print_error "Please update DEVICE_SECRET_KEY in include/config.h before deployment"
        SECURITY_ISSUE=1
    fi

    if grep -q "ai-teddy-bear-v.onrender.com" include/config.h; then
        print_error "Old server URL found in config.h!"
        print_error "Please fix 'ai-teddy-bear-v.onrender.com' to 'ai-tiddy-bear-v-xuqy.onrender.com'"
        SECURITY_ISSUE=1
    fi
else
    print_warning "include/config.h not found - skipping security check"
fi

# 7. REMOVED BUILD TESTING - This was causing the hang
print_status "Skipping build test to avoid LDF hang"
print_warning "Run manual build test after script completion:"
print_warning "  pio run --environment esp32dev-release --dry-run"

# 8. Generate production report
print_status "Generating production readiness report..."

cat > PRODUCTION_READINESS.md << 'EOF'
# Production Readiness Report - FIXED ARCHITECTURE

## 🏭 Build Configuration
- **Environment**: Production
- **SSL/TLS**: Enabled
- **Debug Level**: 0 (Error only)
- **Code Optimization**: -Os (Size optimized)
- **Security Features**: Enabled
- **LDF Mode**: chain (Conservative, prevents hangs)
- **Library Versions**: Pinned (No version conflicts)

## 🔧 Architectural Fixes Applied
- ✅ Changed `lib_ldf_mode` from `chain+` to `chain`
- ✅ Pinned all library versions (removed version ranges)
- ✅ Consistent platform version across environments
- ✅ Removed problematic dependency resolution patterns
- ✅ Eliminated build commands from setup script

## 🔒 Security Checklist
- [ ] Device secret key updated (not default)
- [ ] Server URLs verified and correct
- [ ] SSL certificates configured
- [ ] Debug features disabled
- [ ] Production flags enabled

## 📊 Build Targets
- `esp32dev-release`: Main production build
- `esp32s3dev`: ESP32-S3 production build

## 🚀 Manual Deployment Commands (Post-Setup)
```bash
# Test dependency resolution first
pio run --environment esp32dev-release --dry-run

# Build production firmware (only after dry-run succeeds)
pio run --environment esp32dev-release

# Check memory usage
pio run --environment esp32dev-release --target size

# Upload to device
pio run --environment esp32dev-release --target upload

# Monitor production device
pio device monitor --environment esp32dev-release
```

## ⚠️ Critical Pre-Build Steps
1. Verify network connectivity: `pio pkg search ArduinoJson`
2. Test dependency resolution: `pio run --dry-run`
3. Only proceed to actual build after dry-run succeeds

## 🔍 Troubleshooting
If LDF hang still occurs:
1. Check network/proxy settings
2. Clear global PlatformIO cache: `pio system prune`
3. Verify library registry access
4. Consider reducing library dependencies further

Generated on: $(date)
EOF

print_success "Created PRODUCTION_READINESS.md"

# 9. Final summary
echo ""
echo "🎉 Production preparation completed! (ARCHITECTURAL FIXES APPLIED)"
echo "=================================================================="

if [ "$SECURITY_ISSUE" = "1" ]; then
    print_error "SECURITY ISSUES FOUND!"
    print_error "Please fix the security issues before deployment"
    echo ""
    print_status "Issues to fix:"
    echo "  1. Update DEVICE_SECRET_KEY in include/config.h"
    echo "  2. Fix server URL typos in include/config.h"
    echo ""
    exit 1
fi

print_success "Production environment is ready for testing"
echo ""
print_status "CRITICAL: Test dependency resolution first:"
echo "  pio run --environment esp32dev-release --dry-run"
echo ""
print_status "Only after dry-run succeeds, proceed with:"
echo "  pio run --environment esp32dev-release"
echo ""
print_status "Files modified:"
echo "  - platformio.ini (backup saved as platformio.ini.backup)"
echo "  - Applied architectural fixes for LDF hang prevention"
echo "  - Removed development files and directories"
echo "  - Created PRODUCTION_READINESS.md"
echo ""
print_warning "ARCHITECTURAL CHANGES APPLIED:"
print_warning "  - LDF mode: chain+ → chain"
print_warning "  - Library versions: ranges → pinned"
print_warning "  - Platform versions: unified"

exit 0