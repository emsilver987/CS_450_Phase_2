================================================================================
DEEP TEST COVERAGE ANALYSIS REPORT
================================================================================

Overall Coverage: 65.92%
Total Files Analyzed: 47

================================================================================
CRITICAL COVERAGE GAPS (< 50%)
================================================================================


📄 src/acmecli/cache.py
   Coverage: 0.0% (0/13 lines)
   Missing Lines: 13
   ⚠️  TEST FILE EXISTS BUT NOT COVERING CODE
   Test file: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_cache.py
   Issue: Tests exist but coverage is 0.0%
   Possible causes:
     - Tests use excessive mocking that prevents code execution
     - Tests don't actually import/execute the module
     - Coverage configuration issue
   Recommendation: Review test file and ensure actual code execution

📄 src/acmecli/cli.py
   Coverage: 0.0% (0/106 lines)
   Missing Lines: 106
   ⚠️  TEST FILE EXISTS BUT NOT COVERING CODE
   Test file: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_hf_handler.py
   Issue: Tests exist but coverage is 0.0%
   Possible causes:
     - Tests use excessive mocking that prevents code execution
     - Tests don't actually import/execute the module
     - Coverage configuration issue
   Recommendation: Review test file and ensure actual code execution

📄 src/entrypoint.py
   Coverage: 0.0% (0/9 lines)
   Missing Lines: 9
   ⚠️  TEST FILE EXISTS BUT NOT COVERING CODE
   Test file: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_entrypoint.py
   Issue: Tests exist but coverage is 0.0%
   Possible causes:
     - Tests use excessive mocking that prevents code execution
     - Tests don't actually import/execute the module
     - Coverage configuration issue
   Recommendation: Review test file and ensure actual code execution

📄 src/acmecli/github_handler.py
   Coverage: 7.1% (12/168 lines)
   Missing Lines: 156
   ⚠️  TEST FILE EXISTS BUT NOT COVERING CODE
   Test file: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_github_handler.py
   Issue: Tests exist but coverage is 7.1%
   Possible causes:
     - Tests use excessive mocking that prevents code execution
     - Tests don't actually import/execute the module
     - Coverage configuration issue
   Recommendation: Review test file and ensure actual code execution

📄 src/acmecli/hf_handler.py
   Coverage: 18.9% (34/180 lines)
   Missing Lines: 146
   ⚠️  TEST FILE EXISTS BUT NOT COVERING CODE
   Test file: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_hf_handler.py
   Issue: Tests exist but coverage is 18.9%
   Possible causes:
     - Tests use excessive mocking that prevents code execution
     - Tests don't actually import/execute the module
     - Coverage configuration issue
   Recommendation: Review test file and ensure actual code execution

================================================================================
COVERAGE BY MODULE
================================================================================


📁 src
   Coverage: 60.6% (1198/1977 lines, 2 files)
   ⚠️  Low coverage files:
      - entrypoint.py: 0.0%

📁 src/acmecli
   Coverage: 23.0% (126/549 lines, 7 files)
   ⚠️  Low coverage files:
      - cache.py: 0.0%
      - cli.py: 0.0%
      - github_handler.py: 7.1%
      - hf_handler.py: 18.9%

📁 src/acmecli/metrics
   Coverage: 79.7% (814/1021 lines, 18 files)

📁 src/middleware
   Coverage: 100.0% (34/34 lines, 2 files)

📁 src/routes
   Coverage: 83.5% (370/443 lines, 6 files)

📁 src/services
   Coverage: 70.2% (1802/2566 lines, 8 files)

================================================================================
PRIORITY RECOMMENDATIONS
================================================================================


1. FILES WITH TESTS BUT 0% COVERAGE (HIGH PRIORITY)
   These files have test files but coverage shows 0%. This indicates:
   - Tests may not be executing the actual code
   - Coverage tracking may be misconfigured
   - Tests may be mocking too aggressively

   • src/acmecli/cache.py
     Test: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_cache.py
     Action: Verify tests actually execute code, check coverage config
   • src/acmecli/cli.py
     Test: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_hf_handler.py
     Action: Verify tests actually execute code, check coverage config
   • src/entrypoint.py
     Test: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_entrypoint.py
     Action: Verify tests actually execute code, check coverage config

2. FILES WITH NO TESTS (MEDIUM PRIORITY)


3. FILES WITH LOW COVERAGE BUT EXISTING TESTS

   • src/acmecli/github_handler.py (7.1%)
     Test: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_github_handler.py
     Action: Enhance existing tests to cover missing 156 lines
   • src/acmecli/hf_handler.py (18.9%)
     Test: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_acmecli_hf_handler.py
     Action: Enhance existing tests to cover missing 146 lines

================================================================================
SUMMARY STATISTICS
================================================================================

Total files with < 50% coverage: 5
  - 0% coverage: 3
  - 1-49% coverage: 2
  - Have test files: 5
  - Missing test files: 0

================================================================================
NEXT STEPS
================================================================================

1. Investigate why files with tests show 0% coverage
2. Run tests with coverage to verify tracking works
3. Review test files for files showing 0% coverage
4. Create missing test files for uncovered code
5. Enhance existing tests to improve coverage