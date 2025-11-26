# Test & Coverage Audit – CS_450_Phase_2

**Date:** 2025-01-27  
**Auditor:** AI Assistant  
**Goal:** Identify root causes of CI test failures (0/0 tests, low coverage)

---

## 1. Local pytest (no coverage)

**Command:**

```bash
pytest
```

**Result:**

* Tests collected: **551** (531 passed + 1 failed + 19 skipped)
* Passed: **531**
* Failed: **1** (`tests/integration/test_package_system.py::test_package_download_workflow`)
* Skipped: **19**

**Notes:**

* ✅ No import errors
* ✅ Tests are discovered correctly
* ⚠️ 1 integration test failure (likely environment-specific)
* ⚠️ 33 warnings (mostly deprecation warnings, async mock warnings)

**Key Finding:** `pytest` works fine locally and discovers all tests.

---

## 2. Local pytest with coverage

**Command:**

```bash
pytest --cov=src --cov-report=term-missing
```

**Result:**

* TOTAL coverage: **63%**

**Lowest-coverage important files:**

* `src/services/s3_service.py` – **39%**
* `src/services/rating.py` – **43%**
* `src/services/artifact_storage.py` – **52%**
* `src/routes/system.py` – **57%**
* `src/index.py` – **60%**

**Notes:**

* ✅ Coverage measurement works correctly
* ✅ `--cov=src` covers entire `src/` directory
* ⚠️ Several key service files have low coverage (< 60%)

**Key Finding:** Local coverage is **63%**, not 0% or 22%. The issue is CI-specific.

---

## 3. `./run test` behavior locally

**Command:**

```bash
./run test
```

**Result:**

* Exit code: **1** (failed)
* Tests collected: **0**
* Does coverage run? **No** (fails before coverage)
* Coverage % (if shown): **0%**

**Error from `pytest_output.log`:**

```
/opt/homebrew/opt/python@3.14/bin/python3.14: No module named coverage
```

**Notes:**

* ❌ **CRITICAL:** `./run test` finds **0 tests** and fails with "No module named coverage"
* ❌ The `run` script uses system Python 3.14 (`/opt/homebrew/bin/python3`) which doesn't have `coverage` installed
* ❌ Direct `pytest` uses miniforge3 Python which has all dependencies
* ❌ The script runs `pytest tests/unit` only (not integration tests)
* ❌ Script redirects output to `pytest_output.log`, making debugging harder

**Key Finding:** **This is the root cause!** CI runs `./run test`, which fails because:
1. Coverage module is missing in the Python environment
2. The script may be using a different Python than where dependencies are installed

---

## 4. `run` script inspection

**Path:** `./run`

**test case snippet:**

```bash
run_tests() {
    check_python
    
    # Ensure package is installed in development mode for coverage
    if [[ -f "pyproject.toml" ]]; then
        $PYTHON_CMD -m pip install --quiet --user -e . 2>/dev/null || $PYTHON_CMD -m pip install --quiet -e . 2>/dev/null || true
    fi
    
    # Run tests with coverage on src directory
    if ! SKIP_PROCESSPOOL_TESTS=1 $PYTHON_CMD -m coverage run --source=src -m pytest tests/unit -q --disable-warnings > pytest_output.log 2>&1; then
        # ... error handling ...
    fi
    # ... success handling ...
}
```

**Findings:**

* ✅ Uses `coverage run --source=src -m pytest` (correct source)
* ❌ **Only runs `tests/unit`** (excludes integration tests)
* ❌ Redirects output to log file (hides errors from CI)
* ❌ Uses `$PYTHON_CMD` which may point to wrong Python
* ❌ Doesn't ensure `coverage` is installed before using it
* ⚠️ Complex error parsing logic that may fail silently

**Issues:**

1. **Test path limitation:** Only `tests/unit` is tested, but integration tests exist
2. **Python environment mismatch:** Uses system Python instead of virtualenv Python
3. **Missing dependency check:** Assumes `coverage` is installed
4. **Output redirection:** Errors hidden in log file

---

## 5. CI workflow inspection

**Path:** `.github/workflows/ci.yml`

**Relevant snippet:**

```yaml
jobs:
  install:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: ./run install

  test:
    runs-on: ubuntu-latest
    timeout-minutes: 10
    needs: install
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install dependencies
        run: ./run install
      - name: Run tests
        run: ./run test
```

**Findings:**

* ✅ Uses `./run install` (good)
* ✅ Uses `./run test` (consistent)
* ✅ Python version is set (3.12)
* ✅ No conflicting `working-directory` (runs from repo root)
* ⚠️ **CRITICAL:** The `test` job doesn't reuse the `install` job's environment (separate checkout)
* ⚠️ The `test` job re-runs `./run install`, which may not install dev dependencies (coverage)

**Key Finding:** CI workflow looks correct structurally, but:
- The `test` job is separate from `install`, so it needs to install deps again
- `./run install` may not install `coverage` (it's in `[project.optional-dependencies.dev]`)

---

## 6. Coverage config

**Files:**

* `.coveragerc`: **Yes** (present)
* `pytest.ini`: **Yes** (present)
* `pyproject.toml`: **Yes** (has coverage config)

**.coveragerc snippet:**

```ini
[run]
source = src/acmecli
omit = 
    src/acmecli/cache.py
    src/acmecli/cli.py
    src/acmecli/github_handler.py
    src/acmecli/hf_handler.py

[report]
exclude_lines =
    pragma: no cover
    def __repr__
    raise AssertionError
    raise NotImplementedError
```

**pyproject.toml coverage config:**

```toml
[tool.coverage.run]
source = ["src"]

[tool.coverage.report]
skip_empty = true
```

**Findings:**

* ❌ **CONFLICT:** `.coveragerc` says `source = src/acmecli` (only acmecli subdirectory)
* ✅ `pyproject.toml` says `source = ["src"]` (entire src directory)
* ❌ `run` script uses `--source=src` (matches pyproject.toml, not .coveragerc)
* ⚠️ Coverage tool will use `.coveragerc` if present, overriding command-line `--source`

**Key Finding:** **Configuration conflict!** `.coveragerc` limits coverage to `src/acmecli` only, but:
- The `run` script tries to measure `src/` (entire directory)
- `pyproject.toml` also says `src/`
- Coverage tool prioritizes `.coveragerc`, so it may only measure `acmecli/` subdirectory

This explains why CI might show different coverage numbers!

---

## 7. Summary & Action Plan

### Current status:

* Local pytest: **OK** (531 passed, 1 failed, 19 skipped)
* Local coverage (with `pytest --cov=src`): **63%**
* CI tests: **0/0** (fails immediately)
* CI coverage: **0%** (never runs)

### Root causes (confirmed):

1. **Python environment mismatch in `run` script:**
   - Script uses system Python (`python3`) which may not have `coverage` installed
   - Direct `pytest` uses virtualenv Python (miniforge3) which has all deps
   - CI may have same issue if dependencies aren't installed correctly

2. **Coverage config conflict:**
   - `.coveragerc` limits to `src/acmecli` only
   - `run` script and `pyproject.toml` expect `src/` entire directory
   - This causes inconsistent coverage measurements

3. **Test path limitation:**
   - `run` script only runs `tests/unit`, excluding integration tests
   - This may be intentional, but should be documented

4. **Missing dev dependencies:**
   - `coverage` is in `[project.optional-dependencies.dev]`
   - `./run install` may not install dev dependencies
   - CI needs to explicitly install dev deps

5. **Output redirection:**
   - Errors hidden in `pytest_output.log`
   - CI can't see what's failing

### Next actions:

1. **Fix `run` script test command:**
   ```bash
   # Ensure coverage is installed
   $PYTHON_CMD -m pip install --quiet coverage pytest-cov
   
   # Run all tests (or specify if unit-only is intentional)
   coverage run --source=src -m pytest
   coverage report --fail-under=60
   ```

2. **Fix coverage config conflict:**
   - **Option A:** Delete `.coveragerc` and use `pyproject.toml` only
   - **Option B:** Update `.coveragerc` to `source = src` (match pyproject.toml)
   - **Recommendation:** Use Option A (simpler, one source of truth)

3. **Fix CI workflow:**
   ```yaml
   - name: Install dependencies
     run: |
       ./run install
       python -m pip install --quiet -e ".[dev]"  # Install dev deps including coverage
   ```

4. **Fix Python environment in `run` script:**
   - Use `python` from the active virtualenv if available
   - Or ensure dependencies are installed in the Python being used
   - Consider using `python -m pytest` instead of relying on PATH

5. **Remove output redirection:**
   - Let pytest output go to stdout/stderr so CI can see it
   - Or at least `cat pytest_output.log` on failure

6. **Decide on test scope:**
   - If integration tests should run in CI, change `pytest tests/unit` to `pytest`
   - If unit-only is intentional, document it clearly

---

## 8. Recommended Fixes (Priority Order)

### Priority 1: Fix `run` script (immediate)

```bash
run_tests() {
    check_python
    
    # Install dev dependencies (including coverage)
    if [[ -f "pyproject.toml" ]]; then
        $PYTHON_CMD -m pip install --quiet -e ".[dev]" || {
            echo "Failed to install dev dependencies"
            exit 1
        }
    fi
    
    # Run all tests with coverage
    if ! SKIP_PROCESSPOOL_TESTS=1 $PYTHON_CMD -m coverage run --source=src -m pytest -q --disable-warnings; then
        $PYTHON_CMD -m coverage report -m
        echo "❌ Tests failed!"
        exit 1
    fi
    
    # Report coverage and enforce threshold
    coverage_report=$($PYTHON_CMD -m coverage report -m)
    percent=$(echo "$coverage_report" | grep -E '^TOTAL' | awk '{print $NF}' | tr -d '%' || echo 0)
    total_tests=$(pytest --collect-only -q 2>/dev/null | grep -E 'test session starts|collected' | tail -1 | grep -oE '[0-9]+' | head -1 || echo 0)
    passed_tests=$(echo "$coverage_report" | grep -E 'passed' | wc -l || echo 0)
    
    echo "$coverage_report"
    echo ""
    echo "${passed_tests}/${total_tests} test cases passed. ${percent}% line coverage achieved."
    
    # Enforce minimum coverage
    if (( $(echo "$percent < 60" | bc -l) )); then
        echo "❌ Coverage ${percent}% is below required 60%"
        exit 1
    fi
    
    echo "✅ Tests completed successfully!"
}
```

### Priority 2: Fix coverage config

**Delete `.coveragerc`** (let `pyproject.toml` handle it):

```bash
rm .coveragerc
```

Or update it to match:

```ini
[run]
source = src
omit = 
    src/entrypoint.py
    src/middleware/errorHandler.py
    src/middleware/jwt_auth.py
    # Add other intentionally excluded files
```

### Priority 3: Update CI workflow

```yaml
- name: Install dependencies
  run: |
    ./run install
    python -m pip install --quiet -e ".[dev]"
```

---

## 9. Verification Steps

After applying fixes:

1. **Local verification:**
   ```bash
   ./run test
   ```
   Should show: tests collected, tests passed, coverage > 60%

2. **CI verification:**
   - Push changes
   - Check CI logs for:
     - Tests collected > 0
     - Tests passed > 0
     - Coverage % matches local (within ~5%)

3. **Coverage consistency:**
   ```bash
   pytest --cov=src --cov-report=term-missing | grep TOTAL
   ./run test | grep coverage
   ```
   Both should show similar percentages

---

## 10. Additional Notes

- The `pytest.ini` has `testpaths = tests/unit`, which also limits test discovery
- This may be intentional for faster local runs, but CI should run all tests
- Consider having separate commands: `./run test-unit` and `./run test-all`

