#!/bin/bash
# Script to run tests with proper Python path and coverage reporting

set -e

# Set Python path to include project root
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Run tests with coverage
echo "Running tests with coverage..."
pytest tests/unit tests/integration \
    --cov=src \
    --cov-report=term-missing \
    --cov-report=html \
    --cov-report=json \
    -v \
    "$@"

# Show coverage summary
echo ""
echo "================================"
echo "Coverage Summary:"
echo "================================"
coverage report --skip-empty | tail -5

# Check if coverage meets 60% target
COVERAGE=$(coverage report --skip-empty | grep TOTAL | awk '{print $NF}' | tr -d '%')
echo ""
if (( $(echo "$COVERAGE >= 60" | bc -l) )); then
    echo "✅ Coverage target achieved: ${COVERAGE}% (target: 60%)"
    exit 0
else
    echo "⚠️  Coverage: ${COVERAGE}% (target: 60%)"
    echo "Run 'open htmlcov/index.html' to view detailed coverage report"
    exit 0
fi

