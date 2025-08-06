#!/bin/bash

# AI Teddy Bear - E2E Test Execution Script
# ==========================================
# Comprehensive script for running E2E tests in various environments
# Supports local development, CI/CD, and production validation

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Default values
ENVIRONMENT="local"
TEST_SUITES=""
BASE_URL="http://localhost:8000"
REPORT_DIR="test_reports"
CLEANUP_AFTER="true"
PARALLEL="false"
TIMEOUT="30"
LOG_LEVEL="INFO"

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

# Function to show usage
show_usage() {
    cat << EOF
AI Teddy Bear - E2E Test Runner

Usage: $0 [OPTIONS]

OPTIONS:
    -e, --environment ENV       Test environment (local|ci|staging|production) [default: local]
    -s, --suites SUITES        Test suites to run (comma-separated: child_safety,production_flows,security_performance,error_handling)
    -u, --url URL              Base URL for API testing [default: http://localhost:8000]
    -r, --report-dir DIR       Directory for test reports [default: test_reports]
    -t, --timeout SECONDS     Request timeout in seconds [default: 30]
    -p, --parallel             Run test suites in parallel
    -c, --no-cleanup           Don't clean up test data after tests
    -l, --log-level LEVEL      Log level (DEBUG|INFO|WARNING|ERROR) [default: INFO]
    -h, --help                 Show this help message

EXAMPLES:
    # Run all tests locally
    $0

    # Run only child safety tests in staging
    $0 --environment staging --suites child_safety

    # Run security and performance tests with custom URL
    $0 --suites security_performance,production_flows --url https://api-staging.example.com

    # Run tests in parallel for CI
    $0 --environment ci --parallel --no-cleanup

ENVIRONMENT SETUP:
    Local development:
        - Ensures local services are running
        - Uses test database
        - Full cleanup after tests

    CI/CD:
        - Expects services to be pre-configured
        - Generates CI-friendly reports
        - Strict quality gates

    Staging:
        - Uses staging environment
        - Limited cleanup
        - Performance benchmarking

    Production:
        - Read-only tests only
        - No data modifications
        - Comprehensive monitoring
EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        -s|--suites)
            TEST_SUITES="$2"
            shift 2
            ;;
        -u|--url)
            BASE_URL="$2"
            shift 2
            ;;
        -r|--report-dir)
            REPORT_DIR="$2"
            shift 2
            ;;
        -t|--timeout)
            TIMEOUT="$2"
            shift 2
            ;;
        -p|--parallel)
            PARALLEL="true"
            shift
            ;;
        -c|--no-cleanup)
            CLEANUP_AFTER="false"
            shift
            ;;
        -l|--log-level)
            LOG_LEVEL="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        *)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    local|ci|staging|production)
        ;;
    *)
        print_error "Invalid environment: $ENVIRONMENT"
        show_usage
        exit 1
        ;;
esac

print_status "Starting AI Teddy Bear E2E Tests"
print_status "Environment: $ENVIRONMENT"
print_status "Base URL: $BASE_URL"
print_status "Test Suites: ${TEST_SUITES:-all}"
print_status "Report Directory: $REPORT_DIR"

# Change to project root
cd "$PROJECT_ROOT"

# Create report directory
mkdir -p "$REPORT_DIR"

# Function to check if service is running
check_service() {
    local url=$1
    local service_name=$2
    local max_attempts=30
    local attempt=1
    
    print_status "Checking if $service_name is running..."
    
    while [ $attempt -le $max_attempts ]; do
        if curl -s -f "$url/health" > /dev/null 2>&1; then
            print_success "$service_name is running"
            return 0
        fi
        
        print_status "Attempt $attempt/$max_attempts: Waiting for $service_name..."
        sleep 2
        ((attempt++))
    done
    
    print_error "$service_name is not responding after $max_attempts attempts"
    return 1
}

# Environment-specific setup
setup_environment() {
    case $ENVIRONMENT in
        local)
            print_status "Setting up local environment..."
            
            # Check if Docker is running
            if ! docker info > /dev/null 2>&1; then
                print_error "Docker is not running. Please start Docker."
                exit 1
            fi
            
            # Start local services if needed
            if [ -f "docker-compose.yml" ]; then
                print_status "Starting local services with Docker Compose..."
                docker-compose up -d
                
                # Wait for services to be ready
                sleep 10
            fi
            
            # Check if API is running
            if ! check_service "$BASE_URL" "API Server"; then
                print_error "Local API server is not running"
                exit 1
            fi
            ;;
            
        ci)
            print_status "Setting up CI environment..."
            
            # In CI, services should already be running
            if ! check_service "$BASE_URL" "API Server"; then
                print_error "API server is not available in CI environment"
                exit 1
            fi
            ;;
            
        staging)
            print_status "Setting up staging environment..."
            
            # Check staging services
            if ! check_service "$BASE_URL" "Staging API"; then
                print_error "Staging API is not available"
                exit 1
            fi
            ;;
            
        production)
            print_status "Setting up production environment..."
            print_warning "Running read-only tests in production"
            
            # Check production services
            if ! check_service "$BASE_URL" "Production API"; then
                print_error "Production API is not available"
                exit 1
            fi
            ;;
    esac
}

# Function to run tests with Python
run_python_tests() {
    print_status "Running E2E tests with Python test runner..."
    
    # Build command
    CMD="python -m tests.e2e.test_runner"
    CMD="$CMD --environment $ENVIRONMENT"
    CMD="$CMD --base-url $BASE_URL"
    CMD="$CMD --timeout $TIMEOUT"
    CMD="$CMD --report-dir $REPORT_DIR"
    
    if [ "$PARALLEL" = "true" ]; then
        CMD="$CMD --parallel"
    fi
    
    if [ -n "$TEST_SUITES" ]; then
        # Convert comma-separated to space-separated
        SUITES_ARRAY=(${TEST_SUITES//,/ })
        CMD="$CMD --suites ${SUITES_ARRAY[@]}"
    fi
    
    # Set environment variables
    export LOG_LEVEL="$LOG_LEVEL"
    export TEST_CLEANUP_AFTER="$CLEANUP_AFTER"
    
    print_status "Executing: $CMD"
    
    # Run the tests
    if eval "$CMD"; then
        print_success "E2E tests completed successfully"
        return 0
    else
        print_error "E2E tests failed"
        return 1
    fi
}

# Function to run tests with pytest
run_pytest_tests() {
    print_status "Running E2E tests with pytest..."
    
    # Set pytest configuration
    export PYTEST_CONFIG="tests/e2e/pytest_e2e.ini"
    
    # Build pytest command
    CMD="python -m pytest tests/e2e/"
    CMD="$CMD -c $PYTEST_CONFIG"
    CMD="$CMD --html=$REPORT_DIR/pytest_report.html --self-contained-html"
    CMD="$CMD --junit-xml=$REPORT_DIR/pytest_results.xml"
    
    # Add markers based on test suites
    if [ -n "$TEST_SUITES" ]; then
        MARKERS=""
        IFS=',' read -ra SUITE_ARRAY <<< "$TEST_SUITES"
        for suite in "${SUITE_ARRAY[@]}"; do
            case $suite in
                child_safety)
                    MARKERS="$MARKERS or child_safety"
                    ;;
                production_flows)
                    MARKERS="$MARKERS or production_api"
                    ;;
                security_performance)
                    MARKERS="$MARKERS or security or performance"
                    ;;
                error_handling)
                    MARKERS="$MARKERS or error_handling"
                    ;;
            esac
        done
        
        if [ -n "$MARKERS" ]; then
            # Remove leading " or "
            MARKERS="${MARKERS:4}"
            CMD="$CMD -m \"$MARKERS\""
        fi
    fi
    
    # Add parallel execution if requested
    if [ "$PARALLEL" = "true" ]; then
        CMD="$CMD -n auto"
    fi
    
    # Set environment variables
    export TEST_ENVIRONMENT="$ENVIRONMENT"
    export TEST_BASE_URL="$BASE_URL"
    export TEST_TIMEOUT="$TIMEOUT"
    export TEST_CLEANUP_AFTER="$CLEANUP_AFTER"
    
    print_status "Executing: $CMD"
    
    # Run the tests
    if eval "$CMD"; then
        print_success "Pytest E2E tests completed successfully"
        return 0
    else
        print_error "Pytest E2E tests failed"
        return 1
    fi
}

# Function to generate summary report
generate_summary() {
    local exit_code=$1
    
    print_status "Generating test summary..."
    
    # Find latest reports
    LATEST_JSON_REPORT=$(find "$REPORT_DIR" -name "e2e_comprehensive_report_*.json" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    LATEST_HTML_REPORT=$(find "$REPORT_DIR" -name "e2e_comprehensive_report_*.html" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    LATEST_CICD_REPORT=$(find "$REPORT_DIR" -name "e2e_cicd_report_*.json" -type f -printf '%T@ %p\n' | sort -n | tail -1 | cut -d' ' -f2-)
    
    echo
    echo "=============================================="
    echo "        E2E Test Execution Summary"
    echo "=============================================="
    echo "Environment: $ENVIRONMENT"
    echo "Base URL: $BASE_URL"
    echo "Test Suites: ${TEST_SUITES:-all}"
    echo "Exit Code: $exit_code"
    echo
    echo "Generated Reports:"
    [ -n "$LATEST_JSON_REPORT" ] && echo "  📄 JSON Report: $LATEST_JSON_REPORT"
    [ -n "$LATEST_HTML_REPORT" ] && echo "  🌐 HTML Report: $LATEST_HTML_REPORT"
    [ -n "$LATEST_CICD_REPORT" ] && echo "  🔧 CI/CD Report: $LATEST_CICD_REPORT"
    echo
    
    # Show CI/CD results if available
    if [ -n "$LATEST_CICD_REPORT" ] && [ -f "$LATEST_CICD_REPORT" ]; then
        echo "Quality Gates:"
        python -c "
import json
with open('$LATEST_CICD_REPORT', 'r') as f:
    data = json.load(f)
    gates = data.get('quality_gates', {})
    for gate, details in gates.items():
        if gate.endswith('_passed'):
            status = '✅ PASS' if details else '❌ FAIL'
            gate_name = gate.replace('_passed', '').replace('_', ' ').title()
            print(f'  {gate_name}: {status}')
"
        echo
    fi
    
    if [ $exit_code -eq 0 ]; then
        print_success "All tests passed! 🎉"
    else
        print_error "Some tests failed. Check the reports for details."
    fi
    
    echo "=============================================="
}

# Function to cleanup
cleanup() {
    local exit_code=$?
    
    print_status "Performing cleanup..."
    
    # Environment-specific cleanup
    case $ENVIRONMENT in
        local)
            if [ "$CLEANUP_AFTER" = "true" ]; then
                print_status "Stopping local services..."
                if [ -f "docker-compose.yml" ]; then
                    docker-compose down > /dev/null 2>&1 || true
                fi
            fi
            ;;
    esac
    
    generate_summary $exit_code
    exit $exit_code
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Main execution
main() {
    # Setup environment
    setup_environment
    
    # Check Python environment
    if ! python -c "import sys; assert sys.version_info >= (3, 8)" 2>/dev/null; then
        print_error "Python 3.8+ is required"
        exit 1
    fi
    
    # Install dependencies if needed
    if [ -f "requirements-test.txt" ]; then
        print_status "Installing test dependencies..."
        pip install -r requirements-test.txt > /dev/null 2>&1 || true
    fi
    
    # Try Python test runner first, fall back to pytest
    if ! run_python_tests; then
        print_warning "Python test runner failed, trying pytest..."
        if ! run_pytest_tests; then
            print_error "Both test runners failed"
            exit 1
        fi
    fi
    
    print_success "E2E tests completed successfully!"
}

# Execute main function
main "$@"