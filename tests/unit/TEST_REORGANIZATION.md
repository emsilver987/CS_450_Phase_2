# Test File Reorganization

## Overview

Tests from `test_index.py` have been reorganized by feature/endpoint rather than using "push" naming conventions. This improves maintainability and makes it easier to find tests for specific features.

## New File Structure

### Endpoint/Feature-Based Test Files

1. **`test_endpoints_health.py`** (2.2K)
   - Health component endpoint tests
   - Tests for `/health/components` endpoint

2. **`test_endpoints_artifacts_crud.py`** (25K)
   - Artifact CRUD operations
   - Tests for GET, POST, PUT, DELETE artifact endpoints
   - Edge case tests for CRUD operations

3. **`test_endpoints_artifacts_search.py`** (17K)
   - Artifact search and listing
   - Tests for `/artifact/byName/{name}` endpoint
   - Tests for `/artifact/byRegEx` endpoint
   - S3 metadata lookup tests

4. **`test_endpoints_artifacts_rating.py`** (7.4K)
   - Artifact rating endpoints
   - Tests for `/artifact/model/{id}/rate` endpoint
   - Tests for `/package/{id}/rate` endpoint
   - Async rating tests

5. **`test_endpoints_artifacts_metadata.py`** (15K)
   - Artifact metadata endpoints
   - Tests for cost, audit, lineage, license endpoints
   - Size exception handling tests

6. **`test_endpoints_performance.py`** (4.1K)
   - Performance workload endpoints
   - Tests for `/health/performance/workload` endpoint
   - Performance results retrieval tests

7. **`test_endpoints_helpers.py`** (42K)
   - Helper function tests
   - Utility function tests
   - Dependency parsing, linking, size/rating functions

8. **`test_endpoints_middleware.py`** (2.3K)
   - Middleware and logging tests
   - Logging middleware error handling

9. **`test_endpoints_lifespan.py`** (2.7K)
   - Application lifespan event tests
   - Startup event tests
   - Exception handling during lifespan

10. **`test_endpoints_auth.py`** (2.6K)
    - Authentication token verification tests

11. **`test_endpoints_other.py`** (46K)
    - Miscellaneous endpoint tests
    - Additional coverage tests
    - Edge case tests

### Shared Fixtures

**`test_index_shared.py`**
- Shared fixtures and utilities
- Test client setup
- Mock fixtures (auth, S3, artifact storage)
- Test constants
- Rating state reset fixture

## Migration Notes

- All new test files import from `test_index_shared.py` for shared fixtures
- The original `test_index.py` file is preserved but tests have been extracted
- Tests maintain the same functionality, just reorganized by feature

## Running Tests

Tests can be run individually by feature:

```bash
# Run health endpoint tests
pytest tests/unit/test_endpoints_health.py

# Run artifact CRUD tests
pytest tests/unit/test_endpoints_artifacts_crud.py

# Run all reorganized tests
pytest tests/unit/test_endpoints_*.py
```

## Next Steps

1. Verify all tests pass after reorganization
2. Consider deprecating or removing `test_index.py` if all tests are successfully migrated
3. Review `test_endpoints_other.py` to see if tests can be further categorized
4. Update CI/CD pipelines if they reference specific test files

