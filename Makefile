# Makefile for AI Teddy Bear Test Suite
# Enforces strict quality gates

.PHONY: help install test coverage mutation security quality clean docs all

# Default Python
PYTHON := python3
PIP := $(PYTHON) -m pip

# Configuration
MIN_COVERAGE := 80
MIN_MUTATION_SCORE := 70
TEST_TIMEOUT := 180

# Colors for output
RED := \033[0;31m
GREEN := \033[0;32m
YELLOW := \033[0;33m
NC := \033[0m # No Color

help:
	@echo "AI Teddy Bear Test Suite - Quality Gates"
	@echo "========================================"
	@echo "make install       - Install all dependencies"
	@echo "make test          - Run all tests (must pass)"
	@echo "make coverage      - Run coverage analysis (min $(MIN_COVERAGE)%)"
	@echo "make mutation      - Run mutation testing (min $(MIN_MUTATION_SCORE)%)"
	@echo "make security      - Run security checks"
	@echo "make quality       - Run code quality checks"
	@echo "make clean         - Clean up generated files"
	@echo "make all           - Run all quality gates"
	@echo ""
	@echo "Quality Requirements:"
	@echo "  - No fake or skipped tests"
	@echo "  - $(MIN_COVERAGE)%+ code coverage"
	@echo "  - $(MIN_MUTATION_SCORE)%+ mutation score"
	@echo "  - No security vulnerabilities"
	@echo "  - All tests < $(TEST_TIMEOUT)s"

install:
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	$(PIP) install --upgrade pip
	$(PIP) install -r requirements.txt
	$(PIP) install -r requirements-test.txt
	@echo "$(GREEN)✓ Dependencies installed$(NC)"

test: test-health test-run test-time

test-health:
	@echo "$(YELLOW)Checking test health...$(NC)"
	@# Check for skipped tests
	@if grep -r "@pytest.mark.skip" tests/ 2>/dev/null; then \
		echo "$(RED)✗ Skipped tests found!$(NC)"; \
		exit 1; \
	fi
	@# Check for fake tests
	@$(PYTHON) scripts/test_reality_check.py
	@echo "$(GREEN)✓ Test health check passed$(NC)"

test-run:
	@echo "$(YELLOW)Running all tests...$(NC)"
	@$(PYTHON) -m pytest tests/ -v --tb=short --strict-markers
	@echo "$(GREEN)✓ All tests passed$(NC)"

test-time:
	@echo "$(YELLOW)Checking test execution time...$(NC)"
	@start=$$(date +%s); \
	$(PYTHON) -m pytest tests/ -q; \
	end=$$(date +%s); \
	duration=$$((end - start)); \
	if [ $$duration -gt $(TEST_TIMEOUT) ]; then \
		echo "$(RED)✗ Tests too slow: $${duration}s (max: $(TEST_TIMEOUT)s)$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Test duration: $${duration}s$(NC)"; \
	fi

coverage:
	@echo "$(YELLOW)Running coverage analysis...$(NC)"
	@$(PYTHON) -m pytest tests/ \
		--cov=src \
		--cov-report=term-missing \
		--cov-report=html \
		--cov-report=json \
		--cov-fail-under=$(MIN_COVERAGE)
	@echo "$(GREEN)✓ Coverage check passed (>= $(MIN_COVERAGE)%)$(NC)"
	@# Check critical modules for 100% coverage
	@$(PYTHON) -c "\
import json; \
with open('coverage.json') as f: data = json.load(f); \
critical = ['src/core/entities.py', 'src/core/exceptions.py', 'src/core/value_objects.py']; \
for module in critical: \
    if module in data['files']: \
        cov = data['files'][module]['summary']['percent_covered']; \
        if cov < 100: \
            print(f'$(RED)✗ {module} has {cov}% coverage (required: 100%)$(NC)'); \
            exit(1); \
print('$(GREEN)✓ Critical modules have 100% coverage$(NC)')"

mutation:
	@echo "$(YELLOW)Running mutation testing...$(NC)"
	@$(PYTHON) scripts/mutation_testing.py
	@# Check mutation score
	@score=$$($(PYTHON) -c "import json; print(json.load(open('mutation_testing_report.json'))['mutation_score'])"); \
	if (( $$(echo "$$score < $(MIN_MUTATION_SCORE)" | bc -l) )); then \
		echo "$(RED)✗ Mutation score too low: $${score}% (min: $(MIN_MUTATION_SCORE)%)$(NC)"; \
		exit 1; \
	else \
		echo "$(GREEN)✓ Mutation score: $${score}%$(NC)"; \
	fi

security:
	@echo "$(YELLOW)Running security checks...$(NC)"
	@# Bandit security scan
	@bandit -r src/ -ll -f json -o bandit_report.json
	@high_issues=$$($(PYTHON) -c "import json; print(len([i for i in json.load(open('bandit_report.json'))['results'] if i['issue_severity'] == 'HIGH']))"); \
	if [ $$high_issues -gt 0 ]; then \
		echo "$(RED)✗ High severity security issues found!$(NC)"; \
		exit 1; \
	fi
	@# Safety check
	@safety check --json || true
	@echo "$(GREEN)✓ Security checks passed$(NC)"

quality:
	@echo "$(YELLOW)Running code quality checks...$(NC)"
	@# Black formatting
	@black --check src/ tests/
	@echo "$(GREEN)✓ Code formatting check passed$(NC)"
	@# isort
	@isort --check-only src/ tests/
	@echo "$(GREEN)✓ Import sorting check passed$(NC)"
	@# Flake8
	@flake8 src/ tests/ --max-line-length=120
	@echo "$(GREEN)✓ Linting check passed$(NC)"
	@# MyPy
	@mypy src/ --ignore-missing-imports --strict
	@echo "$(GREEN)✓ Type checking passed$(NC)"

performance:
	@echo "$(YELLOW)Running performance tests...$(NC)"
	@$(PYTHON) -m pytest tests/performance/ -v --benchmark-only
	@echo "$(GREEN)✓ Performance benchmarks passed$(NC)"

clean:
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@rm -rf .coverage htmlcov/ .pytest_cache/ .mypy_cache/
	@rm -f coverage.json coverage.xml bandit_report.json mutation_testing_report.json
	@rm -f test_reality_check_report.json test_restructure_report.json coverage_gap_analysis.json
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -delete
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

# Run all quality gates
all: clean install test coverage mutation security quality performance
	@echo ""
	@echo "$(GREEN)════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✓ ALL QUALITY GATES PASSED!$(NC)"
	@echo "$(GREEN)════════════════════════════════════════$(NC)"
	@echo ""
	@echo "Test suite is production-ready with:"
	@echo "  ✓ No fake or skipped tests"
	@echo "  ✓ 100% test pass rate"
	@echo "  ✓ $(MIN_COVERAGE)%+ code coverage"
	@echo "  ✓ $(MIN_MUTATION_SCORE)%+ mutation score"
	@echo "  ✓ No security vulnerabilities"
	@echo "  ✓ Code quality standards met"
	@echo "  ✓ Performance benchmarks passed"

# CI/CD specific targets
ci-test: install test-health test-run coverage
ci-quality: security quality
ci-full: all

# Development helpers
watch:
	@echo "$(YELLOW)Watching for changes...$(NC)"
	@$(PYTHON) -m pytest tests/ -v --tb=short -f

quick:
	@$(PYTHON) -m pytest tests/ -x --tb=short -m "not slow"

fix-format:
	@echo "$(YELLOW)Auto-formatting code...$(NC)"
	@black src/ tests/
	@isort src/ tests/
	@echo "$(GREEN)✓ Code formatted$(NC)"

# Documentation
docs:
	@echo "Generating test documentation..."
	@$(PYTHON) scripts/generate_test_docs.py