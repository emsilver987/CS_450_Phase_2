================================================================================
DEEP COVERAGE ANALYSIS - ACTIONABLE RECOMMENDATIONS
================================================================================

EXECUTIVE SUMMARY
--------------------------------------------------------------------------------
Overall Coverage: 65.92%
Total Lines: 6590
Covered Lines: 4344

CRITICAL FINDINGS
--------------------------------------------------------------------------------

5 files have < 50% coverage, ALL have test files but show low/zero coverage.
This indicates a coverage tracking or test execution issue.


================================================================================
FILE: src/acmecli/cache.py
================================================================================
Coverage: 0.0% (0/13 lines)
Missing Lines: 10 total
Test File Exists: ❌ NO

ROOT CAUSE ANALYSIS:

ACTIONABLE STEPS:

SOURCE CODE PREVIEW (first 20 lines):
 ⚠️   1: from typing import Dict, Optional
     2: 
     3: 
 ⚠️   4: class InMemoryCache:
     5:     """Simple in-memory cache implementation."""
     6: 
 ⚠️   7:     def __init__(self):
 ⚠️   8:         self._cache: Dict[str, bytes] = {}
 ⚠️   9:         self._etags: Dict[str, str] = {}
    10: 
 ⚠️  11:     def get(self, key: str) -> bytes | None:
    12:         """Get cached data by key."""
 ⚠️  13:         return self._cache.get(key)
    14: 
 ⚠️  15:     def set(self, key: str, data: bytes, etag: str | None = None) -> None:
    16:         """Set cached data with optional etag."""
 ⚠️  17:         self._cache[key] = data
 ⚠️  18:         if etag:
    19:             self._etags[key] = etag
    20: 

================================================================================
FILE: src/acmecli/cli.py
================================================================================
Coverage: 0.0% (0/106 lines)
Missing Lines: 10 total
Test File Exists: ❌ NO

ROOT CAUSE ANALYSIS:

ACTIONABLE STEPS:

SOURCE CODE PREVIEW (first 20 lines):
 ⚠️   1: import sys
 ⚠️   2: from pathlib import Path
 ⚠️   3: import logging
 ⚠️   4: import os
 ⚠️   5: import json
 ⚠️   6: import concurrent.futures
 ⚠️   7: from .types import ReportRow
 ⚠️   8: from .reporter import write_ndjson
 ⚠️   9: from .metrics.base import REGISTRY
 ⚠️  10: from .github_handler import GitHubHandler
    11: from .hf_handler import HFHandler
    12: from .cache import InMemoryCache
    13: from .scoring import compute_net_score
    14: 
    15: 
    16: def setup_logging():
    17:     log_file = os.environ.get("LOG_FILE")
    18:     raw_level = os.environ.get("LOG_LEVEL", "0")
    19:     try:
    20:         log_level = int(raw_level)

================================================================================
FILE: src/entrypoint.py
================================================================================
Coverage: 0.0% (0/9 lines)
Missing Lines: 9 total
Test File Exists: ✅ YES
Test File: /Users/fahdlaniyan/Documents/test/CS_450_Phase_2/tests/unit/test_entrypoint.py

ROOT CAUSE ANALYSIS:
  ⚠️  Tests exist but show 0% coverage. Possible causes:
     1. Tests mock imports instead of executing code
     2. Module-level code not executed during import
     3. Coverage configuration excludes this file
     4. Tests use patching that prevents code execution

ACTIONABLE STEPS:
  1. Verify test file actually imports and executes the module
  2. Check if tests use excessive mocking (patch.object, MagicMock)
  3. Ensure module-level code is executed during test import
  4. Run: pytest tests/unit/test_<module>.py -v --cov=src --cov-report=term-missing
  5. Review coverage report to see which specific lines are missing

SOURCE CODE PREVIEW (first 20 lines):
 ⚠️   1: from __future__ import annotations
     2: 
 ⚠️   3: import os
     4: 
 ⚠️   5: from .index import app as _app
 ⚠️   6: from .middleware.jwt_auth import JWTAuthMiddleware, DEFAULT_EXEMPT
     7: 
     8: # Wrap the original app without modifying existing files
 ⚠️   9: app = _app
    10: 
    11: # Only add JWT middleware if auth is explicitly enabled
    12: # Auth is enabled if ENABLE_AUTH=true OR if JWT_SECRET is set
 ⚠️  13: enable_auth = os.getenv("ENABLE_AUTH", "").lower() == "true"
 ⚠️  14: jwt_secret = os.getenv("JWT_SECRET")
 ⚠️  15: if enable_auth or jwt_secret:
 ⚠️  16:     app.add_middleware(JWTAuthMiddleware, exempt_paths=DEFAULT_EXEMPT)

================================================================================
FILE: src/acmecli/github_handler.py
================================================================================
Coverage: 7.1% (12/168 lines)
Missing Lines: 10 total
Test File Exists: ❌ NO

ROOT CAUSE ANALYSIS:

ACTIONABLE STEPS:

SOURCE CODE PREVIEW (first 20 lines):
     1: import json
     2: import logging
     3: import os
     4: from base64 import b64decode
     5: from urllib.error import HTTPError, URLError
     6: from urllib.request import Request, urlopen
     7: from typing import Any, Dict
     8: 
     9: 
    10: class GitHubHandler:
    11:     """Handler for GitHub repository metadata fetching using stdlib HTTP."""
    12: 
    13:     def __init__(self):
 ⚠️  14:         github_token = os.environ.get("GITHUB_TOKEN")
 ⚠️  15:         self._has_token = bool(
    16:             github_token and github_token != "ghp_test_token_placeholder"
    17:         )
    18:         self._headers = {
 ⚠️  19:             "User-Agent": "ACME-CLI/1.0",
 ⚠️  20:             "Accept": "application/vnd.github.v3+json",

================================================================================
FILE: src/acmecli/hf_handler.py
================================================================================
Coverage: 18.9% (34/180 lines)
Missing Lines: 10 total
Test File Exists: ❌ NO

ROOT CAUSE ANALYSIS:

ACTIONABLE STEPS:

SOURCE CODE PREVIEW (first 20 lines):
     1: import json
     2: import logging
     3: import re
     4: from urllib.error import HTTPError, URLError
     5: from urllib.parse import urlparse
     6: from urllib.request import Request, urlopen
     7: from typing import Dict, List, Set
     8: 
     9: 
    10: class HFHandler:
    11:     def __init__(self) -> None:
    12:         self._headers = {"User-Agent": "ACME-CLI/1.0"}
    13: 
    14:     def _extract_hyperlinks_from_text(self, text: str) -> Dict[str, List[str]]:
    15:         """
    16:         Extract all hyperlinks from README text including:
    17:         - Markdown links: [text](url)
    18:         - Plain URLs: https://example.com
    19:         - HTML links: <a href="url">text</a>
    20:         - Context-aware extraction for common phrases

================================================================================
COVERAGE CONFIGURATION CHECK
================================================================================

Current configuration (from pyproject.toml):
  [tool.coverage.run]
  source = ["src"]

Coverage command (from run script):
  coverage run --source=src -m pytest tests/unit

✅ Configuration looks correct.

================================================================================
IMMEDIATE ACTION ITEMS
================================================================================

1. HIGH PRIORITY: Investigate 0% coverage files with existing tests
   - src/acmecli/cache.py
   - src/acmecli/cli.py
   - src/entrypoint.py
   Action: Run individual test files with coverage to isolate issue

2. MEDIUM PRIORITY: Enhance low coverage files
   - src/acmecli/github_handler.py (7.1%)
   - src/acmecli/hf_handler.py (18.9%)
   Action: Review missing lines and add targeted tests

3. VERIFICATION: Run coverage analysis
   Command: pytest tests/unit/ --cov=src --cov-report=term-missing
   Review output to identify specific uncovered lines
