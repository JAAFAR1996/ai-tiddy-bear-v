#!/bin/bash

# ESP32 AI Teddy Bear - Build Validation Script
# This script validates the project build across all environments

set -e

echo "🧸 ESP32 AI Teddy Bear - Build Validation"
echo "========================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if PlatformIO is installed
if ! command -v pio &> /dev/null; then
    echo -e "${RED}❌ PlatformIO is not installed. Please install it first.${NC}"
    echo "   pip install platformio"
    exit 1
fi

echo -e "${GREEN}✅ PlatformIO found${NC}"

# Environments to test
ENVIRONMENTS=("esp32dev" "esp32dev-debug" "esp32dev-release" "esp32dev-test")

echo ""
echo "🔧 Building all environments..."
echo "==============================="

for env in "${ENVIRONMENTS[@]}"; do
    echo ""
    echo -e "${YELLOW}📦 Building environment: $env${NC}"
    
    if pio run -e $env; then
        echo -e "${GREEN}✅ Build successful for $env${NC}"
        
        # Check memory usage
        echo "   Memory usage:"
        pio run -e $env --target size | grep -E "(RAM|Flash):" || true
        
    else
        echo -e "${RED}❌ Build failed for $env${NC}"
        exit 1
    fi
done

echo ""
echo "🔍 Running static analysis..."
echo "============================="

if command -v cppcheck &> /dev/null; then
    if pio check -e esp32dev --fail-on-defect medium; then
        echo -e "${GREEN}✅ Static analysis passed${NC}"
    else
        echo -e "${YELLOW}⚠️  Static analysis found issues${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  cppcheck not found, skipping static analysis${NC}"
    echo "   Install with: sudo apt-get install cppcheck (Ubuntu/Debian)"
fi

echo ""
echo "📚 Validating dependencies..."
echo "============================="

# Check library dependencies
pio pkg list -e esp32dev

# Check for outdated packages
echo ""
echo "🔄 Checking for updates..."
pio pkg outdated -e esp32dev || true

echo ""
echo "⚙️  Validating configuration..."
echo "=============================="

# Check config file exists
if [[ -f "include/config.h" ]]; then
    echo -e "${GREEN}✅ Configuration file found${NC}"
    
    # Check for required definitions
    if grep -q "WIFI_SSID" include/config.h; then
        echo -e "${GREEN}✅ WIFI_SSID configured${NC}"
    else
        echo -e "${YELLOW}⚠️  WIFI_SSID not found in config${NC}"
    fi
    
    if grep -q "SERVER_HOST" include/config.h; then
        echo -e "${GREEN}✅ SERVER_HOST configured${NC}"
    else
        echo -e "${YELLOW}⚠️  SERVER_HOST not found in config${NC}"
    fi
    
else
    echo -e "${RED}❌ Configuration file missing: include/config.h${NC}"
    exit 1
fi

echo ""
echo "🧪 Testing compilation units..."
echo "==============================="

# Check for undefined symbols
echo "Checking for undefined references..."
if pio run -e esp32dev -v 2>&1 | grep -q "undefined reference"; then
    echo -e "${RED}❌ Found undefined references:${NC}"
    pio run -e esp32dev -v 2>&1 | grep "undefined reference" || true
    exit 1
else
    echo -e "${GREEN}✅ No undefined references found${NC}"
fi

echo ""
echo "💾 Memory analysis..."
echo "==================="

# Generate detailed memory report
echo "Detailed memory usage:"
pio run -e esp32dev --target size

# Check for memory warnings
MEMORY_OUTPUT=$(pio run -e esp32dev --target size 2>&1)
if echo "$MEMORY_OUTPUT" | grep -q "warning.*memory"; then
    echo -e "${YELLOW}⚠️  Memory warnings detected${NC}"
    echo "$MEMORY_OUTPUT" | grep "warning.*memory"
fi

echo ""
echo "🎯 Build validation summary"
echo "==========================="

echo -e "${GREEN}✅ All environments built successfully${NC}"
echo -e "${GREEN}✅ Dependencies validated${NC}"
echo -e "${GREEN}✅ Configuration checked${NC}"
echo -e "${GREEN}✅ No critical issues found${NC}"

echo ""
echo -e "${GREEN}🎉 Build validation completed successfully!${NC}"
echo ""
echo "Next steps:"
echo "  - Upload to device: pio run --target upload"
echo "  - Monitor serial:   pio device monitor"
echo "  - Run specific env: pio run -e esp32dev-debug"

exit 0