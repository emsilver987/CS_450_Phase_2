# Test Coverage Documentation

## Overview

This document describes the test coverage setup for the ACME Registry project, including unit tests, integration tests, and Selenium frontend tests.

## Coverage Configuration

### Current Coverage Target: 60% Line Coverage

Coverage is configured in `.coveragerc` to include:
- `src/` directory (all source files)
- Excludes: CLI scripts, network handlers, and autograder code

### Running Coverage Tests

```bash
# Install dependencies
pip install -r requirements.txt

# Run all tests with coverage
python run.py test

# Or manually with pytest
pytest tests/unit tests/integration --cov=src --cov-report=term-missing --cov-report=html

# View detailed HTML coverage report
open htmlcov/index.html
```

## Test Structure

### Unit Tests (`tests/unit/`)

Unit tests cover individual components:

- **Metrics**: All Phase 1 metrics (bus factor, ramp-up, license, etc.)
- **Services**: 
  - `test_auth_service.py` - Authentication service
  - `test_auth_public.py` - Public authentication endpoints
  - `test_s3_service.py` - S3 storage service
  - `test_rating_service.py` - Package rating service
  - `test_package_service.py` - Package management service
  - `test_validator_service.py` - Package validator service
  - `test_license_compatibility.py` - License compatibility checking
- **Routes**:
  - `test_frontend_routes.py` - Frontend route handlers
  - `test_packages_routes.py` - Package API routes
  - `test_routes_comprehensive.py` - Comprehensive route tests
  - `test_system_routes.py` - System/health routes
- **Middleware**:
  - `test_middleware.py` - JWT authentication middleware
  - `test_jwt_middleware.py` - JWT token handling
  - `test_error_handler.py` - Error handling middleware
- **Core**:
  - `test_index.py` - Main FastAPI app
  - `test_index_comprehensive.py` - Comprehensive API tests
  - `test_entrypoint.py` - Application entrypoint

### Integration Tests (`tests/integration/`)

Integration tests cover system-level functionality:

- **Frontend Tests**:
  - `test_frontend_selenium.py` - Selenium browser tests for all frontend pages
- **AWS Integration**:
  - `test_aws_integration.py` - AWS service integration tests
  - `test_upload.py` - File upload integration
  - `test_directory.py` - Directory listing integration
  - `test_rate_integration.py` - Rating system integration
  - `test_package_system.py` - Package system integration

## Selenium Frontend Tests

### Setup

Selenium tests use Chrome WebDriver with headless mode for CI/CD:

```bash
# Dependencies are in requirements.txt
# webdriver-manager automatically downloads ChromeDriver
pip install selenium webdriver-manager
```

### Running Selenium Tests

```bash
# Run all Selenium tests
pytest tests/integration/test_frontend_selenium.py -v -m selenium

# Run specific test class
pytest tests/integration/test_frontend_selenium.py::TestFrontendPagesWithSelenium -v

# Run with visible browser (for debugging)
# Edit test_frontend_selenium.py and remove --headless from chrome_options
```

### Test Coverage

Selenium tests cover:

1. **Page Accessibility**:
   - Home page
   - Directory page
   - Upload page
   - Rate page
   - Admin page
   - Lineage page
   - Size cost page
   - Ingest page
   - License check page

2. **User Interactions**:
   - Directory search with query parameters
   - Directory search with regex patterns
   - File upload validation
   - Form submissions

3. **Error Handling**:
   - Error states for all pages
   - Missing data handling
   - API error handling

## Coverage Goals

### Current Status

- **Target**: 60% line coverage
- **Scope**: All source files in `src/` (routes, services, middleware)
- **Exclusions**: CLI scripts, network handlers, autograder code

### Areas Covered

- ✅ Routes (frontend, packages, artifacts, system)
- ✅ Services (auth, rating, s3, package, validator, license)
- ✅ Middleware (JWT auth, error handling)
- ✅ Metrics (all Phase 1 metrics)
- ✅ Frontend pages (Selenium tests)

### Areas for Improvement

To increase coverage beyond 60%:

1. Add more edge case tests for services
2. Add error path tests for routes
3. Add integration tests for complex workflows
4. Add tests for error handling scenarios
5. Add tests for authentication edge cases

## CI/CD Integration

Tests run automatically in CI/CD:

```yaml
# .github/workflows/ci.yml
- name: Run tests with coverage
  run: |
    pip install -r requirements.txt
    pytest tests/unit tests/integration --cov=src --cov-report=xml
```

## Test Markers

Tests are organized with markers:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.selenium` - Selenium browser tests

Run tests by marker:

```bash
pytest -m unit
pytest -m integration
pytest -m selenium
```

## Notes

- Selenium tests use TestClient for fast execution but can be configured to use actual browser
- Coverage excludes network-heavy modules to avoid flaky tests
- Integration tests may require AWS credentials or mocks
- Frontend tests use mocked services to avoid external dependencies

