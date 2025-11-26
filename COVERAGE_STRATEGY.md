# Coverage Improvement Strategy

## Current State

- **Total**: 6115 lines, 4127 missed → **33% covered**
- **Target**: 60% coverage
- **Gap**: Need to cover ~1.6k more lines

## Priority Analysis

### Tier 1: High Impact Files (Focus Here First)

These files have the most uncovered lines and will give the biggest coverage boost:

1. **`src/index.py`** - 1968 stmts, **17%** (1634 missed)
   - **Impact**: Covering 500 lines here = ~8% overall improvement
   - **Strategy**: Test main endpoints (POST /artifacts, GET /artifact/byName, POST /artifact/byRegEx, GET /artifact/{type}/{id}, POST /artifact/ingest, etc.)
   - **Estimated gain**: 400-500 lines

2. **`src/services/s3_service.py`** - 1072 stmts, **11%** (952 missed)
   - **Impact**: Covering 400 lines here = ~6.5% overall improvement
   - **Strategy**: Test core S3 operations (list_models, upload_model, download_model, model_ingestion)
   - **Estimated gain**: 300-400 lines

3. **`src/services/rating.py`** - 422 stmts, **20%** (339 missed)
   - **Impact**: Covering 200 lines here = ~3% overall improvement
   - **Strategy**: Test run_scorer, analyze_model_content, metric calculations
   - **Estimated gain**: 150-200 lines

### Tier 2: Medium Impact Files

4. **`src/routes/packages.py`** - 158 stmts, **43%** (90 missed)
   - **Strategy**: Test remaining endpoints (search, advanced_search, upload/download)
   - **Estimated gain**: 60-80 lines

5. **`src/routes/frontend.py`** - 196 stmts, **28%** (142 missed)
   - **Strategy**: Test frontend route handlers
   - **Estimated gain**: 100-120 lines

6. **`src/services/license_compatibility.py`** - 239 stmts, **46%** (128 missed)
   - **Strategy**: Test license extraction and compatibility checks
   - **Estimated gain**: 80-100 lines

7. **`src/services/validator_service.py`** - 146 stmts, **45%** (80 missed)
   - **Strategy**: Test validation logic
   - **Estimated gain**: 50-70 lines

### Tier 3: Quick Wins (Low Effort, Good Coverage)

8. **`src/middleware/errorHandler.py`** - 6 stmts, **0%** (6 missed)
   - **Strategy**: Single test for error handler
   - **Estimated gain**: 6 lines

9. **`src/middleware/jwt_auth.py`** - 28 stmts, **0%** (28 missed)
   - **Strategy**: Test JWT middleware paths
   - **Estimated gain**: 28 lines

10. **`src/services/auth_public.py`** - 49 stmts, **33%** (33 missed)
    - **Strategy**: Test authentication endpoints
    - **Estimated gain**: 25-30 lines

### Tier 4: Metric Files (Lower Priority)

11. **`src/acmecli/metrics/treescore_metric.py`** - 265 stmts, **5%** (253 missed)
    - **Strategy**: Test tree scoring logic
    - **Estimated gain**: 100-150 lines (but complex)

12. **`src/acmecli/metrics/score_dependencies.py`** - 42 stmts, **21%** (33 missed)
    - **Strategy**: Test dependency scoring
    - **Estimated gain**: 25-30 lines

13. **`src/acmecli/metrics/score_pull_requests.py`** - 30 stmts, **20%** (24 missed)
    - **Strategy**: Test PR scoring
    - **Estimated gain**: 20-25 lines

## Recommended Testing Order

### Phase 1: Quick Wins (Target: +100 lines, ~2% improvement)

1. ✅ `src/middleware/errorHandler.py` - 6 lines
2. ✅ `src/middleware/jwt_auth.py` - 28 lines
3. ✅ `src/services/auth_public.py` - 30 lines
4. ✅ `src/routes/packages.py` (remaining) - 40 lines
   **Total Phase 1**: ~104 lines → **35% coverage**

### Phase 2: High-Impact Core Services (Target: +400 lines, ~6.5% improvement)

1. ✅ `src/services/s3_service.py` - Core operations (300 lines)
2. ✅ `src/services/rating.py` - Main scoring functions (100 lines)
   **Total Phase 2**: ~400 lines → **41.5% coverage**

### Phase 3: Main Application Endpoints (Target: +500 lines, ~8% improvement)

1. ✅ `src/index.py` - Main endpoints:
   - POST /artifacts
   - GET /artifact/byName/{name}
   - POST /artifact/byRegEx
   - GET /artifact/{type}/{id}
   - POST /artifact/ingest
   - GET /artifact/{type}/{id}/cost
   - GET /artifact/{type}/{id}/audit
   - GET /artifact/model/{id}/rate
   - GET /artifact/model/{id}/lineage
   - POST /artifact/model/{id}/license-check
     **Total Phase 3**: ~500 lines → **49.5% coverage**

### Phase 4: Supporting Services (Target: +200 lines, ~3% improvement)

1. ✅ `src/services/license_compatibility.py` - 100 lines
2. ✅ `src/services/validator_service.py` - 70 lines
3. ✅ `src/routes/frontend.py` - 30 lines
   **Total Phase 4**: ~200 lines → **52.5% coverage**

### Phase 5: Metrics & Polish (Target: +200 lines, ~3% improvement)

1. ✅ `src/acmecli/metrics/score_dependencies.py` - 30 lines
2. ✅ `src/acmecli/metrics/score_pull_requests.py` - 25 lines
3. ✅ `src/acmecli/metrics/treescore_metric.py` - 100 lines
4. ✅ Additional edge cases in covered files - 45 lines
   **Total Phase 5**: ~200 lines → **55.5% coverage**

### Phase 6: Final Push to 60% (Target: +150 lines, ~2.5% improvement)

1. ✅ Additional edge cases in `src/index.py` - 100 lines
2. ✅ Additional edge cases in `src/services/s3_service.py` - 50 lines
   **Total Phase 6**: ~150 lines → **58% coverage**

## Testing Strategy Per File

### `src/index.py` Testing Plan

**Priority endpoints to test:**

1. `POST /artifacts` - List artifacts with filters
2. `GET /artifact/byName/{name}` - Get artifact by name
3. `POST /artifact/byRegEx` - Search by regex
4. `GET /artifact/{type}/{id}` - Get artifact by type and ID
5. `POST /artifact/ingest` - Ingest artifact
6. `GET /artifact/{type}/{id}/cost` - Get cost
7. `GET /artifact/{type}/{id}/audit` - Get audit
8. `GET /artifact/model/{id}/rate` - Rate model
9. `GET /artifact/model/{id}/lineage` - Get lineage
10. `POST /artifact/model/{id}/license-check` - License check

**Helper functions:**

- `_link_model_to_datasets_code`
- `_link_dataset_code_to_models`
- `_extract_dataset_code_names_from_readme`
- `_get_model_name_for_s3`
- `verify_auth_token`

### `src/services/s3_service.py` Testing Plan

**Priority functions:**

1. `list_models` - With various filters
2. `upload_model` - Upload flow
3. `download_model` - Download flow
4. `model_ingestion` - Ingestion process
5. `list_artifacts_from_s3` - List artifacts
6. `get_model_lineage_from_config` - Lineage extraction
7. `get_model_sizes` - Size calculation

### `src/services/rating.py` Testing Plan

**Priority functions:**

1. `run_scorer` - Main scoring function
2. `analyze_model_content` - Content analysis
3. Metric calculation helpers

## Implementation Notes

1. **Use mocking** for AWS services (S3, DynamoDB) to avoid external dependencies
2. **Test error paths** - HTTPException cases, validation failures
3. **Test edge cases** - Empty inputs, None values, boundary conditions
4. **Use fixtures** for common test data
5. **Group related tests** in test classes

## Success Metrics

- **Current**: 33% coverage (1988/6115 lines)
- **Target**: 60% coverage (3669/6115 lines)
- **Gap**: 1681 lines to cover
- **Estimated effort**: ~6 phases, each phase ~100-500 lines

## Next Steps

1. Start with Phase 1 (Quick Wins) - Easy, high ROI
2. Move to Phase 2 (Core Services) - High impact
3. Continue with Phase 3 (Main Endpoints) - Critical paths
4. Complete remaining phases to reach 60%
