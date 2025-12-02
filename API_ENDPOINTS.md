# ACME Registry API Endpoints

This document lists all available API endpoints, their HTTP methods, and payload options.

## Health & System Endpoints

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/health` | GET | None |
| `/health/components` | GET | None |
| `/health/performance/workload` | POST | JSON body: `{"num_clients": int, "model_id": string, "artifact_id": string (optional), "duration_seconds": int (optional)}` |
| `/health/performance/results/{run_id}` | GET | Path parameter: `run_id` (string) |

## Authentication

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/authenticate` | PUT | JSON body: `{"user": {"name": string, "is_admin": boolean}, "secret": {"password": string}}` |

## Registry Management

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/reset` | DELETE | Headers: `X-Authorization` (optional) |
| `/reset-rds` | DELETE | Headers: `X-Authorization` (optional) |

## Artifacts

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/artifacts` | POST | JSON body: Artifact metadata |
| `/artifact/{artifact_type}/{id}` | GET | Query parameters: None |
| `/artifacts/{artifact_type}/{id}` | GET | Query parameters: None |
| `/artifact/{artifact_type}` | POST | JSON body: Artifact data |
| `/artifacts/{artifact_type}/{id}` | PUT | JSON body: Updated artifact data |
| `/artifacts/{artifact_type}/{id}` | DELETE | Headers: `X-Authorization` (optional) |
| `/artifact/{artifact_type}/{id}/cost` | GET | Query parameters: None |
| `/artifact/{artifact_type}/{id}/audit` | GET | Query parameters: None |
| `/artifact/byName/{name}` | GET | Query parameters: `name` (path parameter) |
| `/artifact/byRegEx` | POST | JSON body: `{"nameRegex": string (optional), "versionRange": string (optional)}` |
| `/artifact/ingest` | POST | JSON body or form data: `{"name": string, "version": string, "type": string}` |

## Model-Specific Endpoints

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/artifact/model/{id}/rate` | GET | Query parameters: `id` (path parameter) |
| `/artifact/model/{id}/lineage` | GET | Query parameters: `id` (path parameter) |
| `/artifact/model/{id}/license-check` | POST | JSON body: License compatibility check data |
| `/artifact/model/{id}/download` | GET | Query parameters: `version` (default: "main"), `component` (default: "full"), `path_prefix` (default: "models") |
| `/artifact/model/{id}/download-rds` | GET | Query parameters: `version` (default: "main"), `component` (default: "full"), `path_prefix` (default: "models") |
| `/artifact/model/{id}/upload-rds` | POST | Multipart form data: `file` (required), Query parameters: `version` (default: "main"), `path_prefix` (default: "models") |
| `/artifact/model/{id}/upload-rds-url` | GET | Query parameters: `version` (default: "main"), `path_prefix` (default: "performance"), `expires_in` (default: 3600) |
| `/artifact/model/{id}/upload-rds-from-s3` | POST | Query parameters: `s3_key` (required), `version` (default: "main"), `path_prefix` (default: "performance") |
| `/artifact/model/{id}/check-rds` | GET | Query parameters: `version` (default: "main"), `path_prefix` (default: "performance") |

## Package Endpoints

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/package/{id}` | GET | Query parameters: `id` (path parameter) |
| `/package/{id}/rate` | GET | Query parameters: `id` (path parameter) |

## Tracks

| Endpoint | Verb(s) | Payload option(s) |
|----------|---------|-------------------|
| `/tracks` | GET | Query parameters: None |

## Notes

- All endpoints support optional authentication via `X-Authorization` or `Authorization` header
- Query parameters with default values can be omitted
- Path parameters are required (e.g., `{id}`, `{artifact_type}`, `{name}`)
- RDS endpoints (`/upload-rds`, `/download-rds`, `/reset-rds`) require RDS credentials to be configured
- S3 endpoints (`/download`) use S3 storage backend
- The `path_prefix` parameter accepts `"models"` or `"performance"` (default: `"models"`)
- The `component` parameter accepts `"full"`, `"weights"`, or `"datasets"` (default: `"full"`)

