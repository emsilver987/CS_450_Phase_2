# CloudFront Configuration for ACME Registry

## Overview
CloudFront is configured to serve both the frontend and API endpoints, routing requests to either the ALB (Application Load Balancer) or API Gateway based on the path pattern.

## Origins

### 1. ALB Origin (`alb-origin`)
- **Domain**: Application Load Balancer DNS name
- **Protocol**: HTTP (CloudFront handles HTTPS termination)
- **Purpose**: Serves frontend pages and most API endpoints

### 2. API Gateway Origin (`api-gateway-origin`)
- **Domain**: API Gateway invoke URL domain
- **Protocol**: HTTPS
- **Purpose**: Serves `/api/*` endpoints (alternative API endpoint)

## Cache Behaviors (Order Matters!)

CloudFront evaluates cache behaviors in order, from most specific to least specific:

### 1. Static Assets (`/static/*`)
- **Origin**: ALB
- **Cache**: 1 day (86400s) to 1 year (31536000s)
- **Methods**: GET, HEAD, OPTIONS
- **Purpose**: Cache static files (CSS, JS, images)

### 2. API Gateway Routes (`/api/*`)
- **Origin**: API Gateway
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: API endpoints via API Gateway

### 3. Artifact Routes (`/artifact/*`)
- **Origin**: ALB
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: Artifact management endpoints

### 4. Health Endpoints (`/health*`)
- **Origin**: ALB
- **Cache**: 1 minute (60s) to 5 minutes (300s)
- **Methods**: GET, HEAD, OPTIONS
- **Purpose**: Health check endpoints

### 5. Authentication (`/authenticate*`)
- **Origin**: ALB
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: Authentication endpoints

### 6. Artifacts (`/artifacts*`)
- **Origin**: ALB
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: Artifacts listing/management

### 7. Auth Routes (`/auth/*`)
- **Origin**: ALB
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: User authentication (register, login, logout)

### 8. Frontend Routes
The following routes are configured with no cache:
- `/upload*` - File upload interface
- `/rate*` - Model rating interface
- `/directory*` - Model directory listing
- `/admin*` - Admin interface
- `/ingest*` - Model ingestion interface
- `/download/*` - Model download endpoints
- `/lineage*` - Model lineage interface
- `/size-cost*` - Size and cost information
- `/reset*` - Reset operations
- `/tracks*` - Tracking endpoints

### 9. Default Behavior
- **Origin**: ALB
- **Cache**: No cache (TTL = 0)
- **Methods**: All HTTP methods
- **Purpose**: Catch-all for all other routes (frontend pages, root, etc.)

## Key Configuration Details

### Headers Forwarded
- **All headers** (`["*"]`) are forwarded for API endpoints to ensure:
  - Authentication tokens work correctly
  - CORS headers are preserved
  - Content-Type and other request metadata is passed through

### Query Strings
- **All query strings** are forwarded for API endpoints to support:
  - Filtering and pagination
  - Search parameters
  - Rate limiting parameters

### Cookies
- **All cookies** are forwarded for authenticated endpoints
- **No cookies** for static assets (performance optimization)

### HTTPS
- **Viewer Protocol Policy**: `redirect-to-https`
- All HTTP requests are automatically redirected to HTTPS

### Error Handling
- **404 errors**: Redirected to `/` (for SPA routing)
- **403 errors**: Redirected to `/` (for SPA routing)

## Route Mapping

| Localhost Route | CloudFront Route | Origin | Cache |
|----------------|------------------|--------|-------|
| `/api/*` | `/api/*` | API Gateway | None |
| `/artifact/*` | `/artifact/*` | ALB | None |
| `/artifacts*` | `/artifacts*` | ALB | None |
| `/health*` | `/health*` | ALB | 1 min |
| `/authenticate*` | `/authenticate*` | ALB | None |
| `/auth/*` | `/auth/*` | ALB | None |
| `/upload` | `/upload*` | ALB | None |
| `/rate` | `/rate*` | ALB | None |
| `/directory` | `/directory*` | ALB | None |
| `/admin` | `/admin*` | ALB | None |
| `/ingest` | `/ingest*` | ALB | None |
| `/download/{model_id}/{version}` | `/download/*` | ALB | None |
| `/static/*` | `/static/*` | ALB | 1 day |
| `/` (root) | `/` | ALB | None |

## Testing

After deploying CloudFront, test that all routes work correctly:

1. **Health Check**: `https://<cloudfront-domain>/health`
2. **API Endpoint**: `https://<cloudfront-domain>/api/hello`
3. **Frontend**: `https://<cloudfront-domain>/directory`
4. **Upload**: `https://<cloudfront-domain>/upload`
5. **Rate**: `https://<cloudfront-domain>/rate?name=model-name`

## Deployment

The CloudFront distribution is created via Terraform in:
- `infra/modules/cloudfront/main.tf`
- `infra/envs/dev/main.tf` (module instantiation)

After applying Terraform, the CloudFront URL will be available in the outputs:
- `cloudfront_url`: Full HTTPS URL
- `cloudfront_domain_name`: Domain name only
- `cloudfront_distribution_id`: Distribution ID for management

## Notes

- CloudFront distributions can take 15-20 minutes to deploy
- Cache invalidation may be needed after code updates (use `aws cloudfront create-invalidation`)
- The default behavior catches all unmatched routes and routes them to the ALB
- All API endpoints have no cache to ensure real-time data


