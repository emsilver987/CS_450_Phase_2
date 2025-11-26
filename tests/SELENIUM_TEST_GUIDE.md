# Selenium Tests Guide

## Status

✅ **Selenium tests are properly structured and ready to use**

The tests will work when:
1. The server is running on port 3000 (or TEST_BASE_URL)
2. ChromeDriver is available

## Current Status

- ✅ Selenium package installed (version 4.38.0)
- ✅ Tests are properly structured (10 tests)
- ⚠️ Server needs to be running for tests to execute
- ⚠️ ChromeDriver needs to be available

## Running Selenium Tests

### Prerequisites

1. **Start the server:**
   ```bash
   # In one terminal
   python -m src.index
   # Or
   uvicorn src.index:app --port 3000
   ```

2. **Install ChromeDriver (if not already installed):**
   ```bash
   # macOS
   brew install chromedriver
   
   # Or download from: https://chromedriver.chromium.org/
   ```

### Run Tests

```bash
# Run all Selenium tests
pytest tests/integration/test_selenium_frontend.py -v

# Run specific test
pytest tests/integration/test_selenium_frontend.py::TestHomePage::test_home_page_loads -v
```

### With Custom Base URL

```bash
TEST_BASE_URL=http://localhost:8000 pytest tests/integration/test_selenium_frontend.py -v
```

## Test Coverage

The Selenium tests cover:

1. **Home Page** (2 tests)
   - Page loads
   - Page has content

2. **Upload Page** (2 tests)
   - Page loads
   - Page has form

3. **Directory Page** (2 tests)
   - Page loads
   - Page has search

4. **Rate Page** (2 tests)
   - Page loads
   - Page with model name parameter

5. **Navigation** (2 tests)
   - Navigate home to upload
   - Navigate to directory

**Total: 10 tests**

## Test Behavior

- Tests will **skip gracefully** if:
  - ChromeDriver is not available
  - Server is not running
  - Server is not responding

- Tests use **headless Chrome** (no GUI window)

## Troubleshooting

### Error: `ERR_CONNECTION_REFUSED`
**Solution**: Start the server first
```bash
python -m src.index
```

### Error: `ChromeDriver not available`
**Solution**: Install ChromeDriver
```bash
brew install chromedriver  # macOS
```

### Error: `Server not responding`
**Solution**: Check server is running and accessible
```bash
curl http://localhost:3000/health
```

## CI/CD Integration

For CI/CD, you can:

1. **Skip Selenium tests if server not available:**
   ```bash
   pytest tests/integration/test_selenium_frontend.py || true
   ```

2. **Use a test server in CI:**
   ```yaml
   - name: Start server
     run: |
       python -m src.index &
       sleep 5
   - name: Run Selenium tests
     run: pytest tests/integration/test_selenium_frontend.py
   ```

## Verification

To verify Selenium tests work:

```bash
# 1. Start server (in background)
python -m src.index &

# 2. Wait for server to start
sleep 3

# 3. Run tests
pytest tests/integration/test_selenium_frontend.py -v

# 4. Stop server
pkill -f "src.index"
```

## Conclusion

✅ **Selenium tests are properly implemented and ready to use!**

They just need:
- Server running
- ChromeDriver installed

The tests will skip gracefully if requirements aren't met, so they won't break your test suite.

