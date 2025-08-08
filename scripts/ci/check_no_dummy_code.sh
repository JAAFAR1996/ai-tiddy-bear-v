#!/usr/bin/env bash
set -e

# Create reports directory if it doesn't exist
mkdir -p reports

# Define patterns to search for dummy/mock/fake code
PATTERNS=(
    "TODO.*dummy"
    "TODO.*mock"
    "TODO.*fake"
    "FIXME.*dummy"
    "FIXME.*mock"
    "FIXME.*fake"
    "dummy.*data"
    "mock.*data"
    "fake.*data"
    "placeholder.*code"
    "test.*dummy"
    "dummy.*implementation"
    "mock.*implementation"
    "fake.*implementation"
)

# Output file
OUTPUT_FILE="reports/dummy_references.log"
echo "Scanning for dummy/mock/fake code patterns..." > "$OUTPUT_FILE"
echo "========================================" >> "$OUTPUT_FILE"

FOUND_ISSUES=0

# Search for each pattern in src directory
for pattern in "${PATTERNS[@]}"; do
    echo "Checking pattern: $pattern" >> "$OUTPUT_FILE"
    if rg -i "$pattern" src/ --line-number --with-filename >> "$OUTPUT_FILE" 2>/dev/null; then
        FOUND_ISSUES=1
    fi
    echo "" >> "$OUTPUT_FILE"
done

if [ $FOUND_ISSUES -eq 1 ]; then
    echo "❌ Dummy/mock/fake code patterns found! Check $OUTPUT_FILE for details."
    exit 1
else
    echo "✅ No dummy/mock/fake code patterns detected."
    echo "No issues found." >> "$OUTPUT_FILE"
    exit 0
fi