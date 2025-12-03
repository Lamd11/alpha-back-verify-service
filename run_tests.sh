#!/bin/bash
# Test runner script for AlphaBack Verify Service
# Runs all tests with coverage reporting

set -e

echo "=========================================="
echo "AlphaBack Verify Service - Test Suite"
echo "=========================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "pytest not found. Installing dependencies..."
    pip install -r requirements.txt
fi

# Run unit tests
echo -e "${BLUE}Running Unit Tests...${NC}"
echo ""
pytest tests/test_report_generator.py tests/test_java_bytecode_scanner.py tests/test_lambda_function.py -v

echo ""
echo -e "${BLUE}Running Integration Tests...${NC}"
echo ""
pytest tests/test_integration.py -v

# Run all tests with coverage
echo ""
echo -e "${BLUE}Running All Tests with Coverage...${NC}"
echo ""
pytest

# Generate coverage summary
echo ""
echo -e "${GREEN}=========================================="
echo "Test Coverage Report"
echo -e "==========================================${NC}"
echo ""
echo "HTML report generated at: htmlcov/index.html"
echo "JSON report generated at: coverage.json"
echo ""
echo -e "${GREEN}✓ All tests completed!${NC}"
