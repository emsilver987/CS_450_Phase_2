# Increase Coverage to 60%

**Goal**: Raise overall test coverage from 50% to at least 60% by adding targeted tests for the remaining large uncovered blocks in `src/index.py` (lines 2966-3128, 3289-3398) and `src/services/s3_service.py` (lines 1320-1684). This also includes fixing the failing tests in `tests/unit/test_services_strategic.py` and `tests/integration/test_rate_integration.py`.

## User Review Required
- **Confirm** that adding new tests is acceptable without modifying production code.
- **Approve** the plan to run the full test suite after adding tests.
- If there are any constraints on test execution time or CI resources, let me know.

## Proposed Changes
### Test Additions
- **`tests/unit/test_index_remaining_blocks.py`**: Tests covering audit trail logic, version fallback, S3 key handling, date parsing, and helper functions.
- **`tests/unit/test_s3_service_remaining.py`**: Tests for GitHub URL extraction patterns, metadata creation, model ingestion flow, and error handling across the large block.
- **`tests/unit/test_services_strategic_fix.py`**: Adjustments/mocks to resolve current failing tests.
- **`tests/integration/test_rate_integration_fix.py`**: Mock external scorer to avoid real execution failures.

### Test Enhancements
- Refactor existing failing tests to use proper mocks for DynamoDB and S3.
- Ensure all new tests are deterministic and run quickly.

## Verification Plan
1. **Run full test suite**:
   ```bash
   PYTHONPATH=.:src SKIP_PROCESSPOOL_TESTS=1 .venv/bin/python -m coverage run -m pytest tests/unit tests/integration -q --disable-warnings
   ```
2. **Generate coverage report** and verify `TOTAL` coverage >= 60%:
   ```bash
   .venv/bin/python -m coverage report | grep TOTAL
   ```
3. **Check that previously failing tests now pass** (expect 0 failures).
4. **Commit changes** and ensure CI passes.

## Verification Details
- Each new test file will be executed via the above command.
- Coverage will be measured for the entire project; we will specifically confirm `src/index.py` and `src/services/s3_service.py` reach >55% each.
- Any remaining failures will be reported back for further debugging.
