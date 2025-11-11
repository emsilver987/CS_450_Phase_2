# Deployment Instructions

## Summary of Changes

✅ **Fixed:** Frontend routes registration in `src/index.py`
- Added call to `register_routes(app)` after templates are loaded
- This ensures frontend pages (`/`, `/directory`, `/upload`, `/rate`) are accessible

## Current Status

- ✅ **Localhost:** All endpoints working (tested successfully)
- ❌ **AWS Services:** Still showing 404 errors (needs Docker rebuild and redeploy)

## Next Steps to Deploy Fix

### Prerequisites
1. **Docker Desktop must be running**
   - Start Docker Desktop application
   - Wait for it to fully start (whale icon in system tray)

2. **AWS CLI configured**
   - Ensure AWS credentials are set up
   - Verify with: `aws sts get-caller-identity`

### Deployment Steps

1. **Start Docker Desktop**
   ```powershell
   # Check if Docker is running
   docker ps
   ```

2. **Rebuild and Redeploy**
   ```powershell
   cd C:\Users\Taiwo\OneDrive\Documents\CSCI\debug\CS_450_Phase_2
   .\redeploy_service.ps1
   ```

   This script will:
   - Login to ECR
   - Build Docker image with frontend routes fix
   - Tag and push to ECR
   - Force ECS service update
   - Wait for service to stabilize

3. **Wait for Deployment** (5-10 minutes)
   - ECS will pull the new image
   - Service will restart with new code
   - ALB health checks will verify service is healthy

4. **Test the Deployment**
   ```powershell
   .\test_all_services.ps1
   ```

   Or test manually:
   - CloudFront: `https://d3evfv0v7o5aro.cloudfront.net/`
   - ALB: `http://validator-lb-727503296.us-east-1.elb.amazonaws.com/`

## What Was Fixed

**File:** `src/index.py`

**Before:**
```python
templates = (
    Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None
)
# Frontend routes were NOT registered!
```

**After:**
```python
templates = (
    Jinja2Templates(directory=str(TEMPLATES_DIR)) if TEMPLATES_DIR.exists() else None
)

# 5) Register frontend routes (home, directory, upload, etc.)
if templates:
    from .routes.frontend import register_routes, set_templates
    set_templates(templates)  # Set templates in frontend module
    register_routes(app)  # Register all frontend routes
```

## Verification

After deployment, test these endpoints:

- ✅ `/health` - Should return 200
- ✅ `/` - Should return home page (not 404)
- ✅ `/directory` - Should return directory page
- ✅ `/upload` - Should return upload page
- ✅ `/rate` - Should return rate page
- ✅ `/api/hello` - Should return API response

## Troubleshooting

### Docker Not Running
- Start Docker Desktop
- Wait for it to fully initialize
- Run `docker ps` to verify

### ECS Service Not Updating
- Check ECS console for service status
- Verify task definition is using latest image
- Check CloudWatch logs for errors

### Still Getting 404 Errors
- Wait 5-10 minutes for CloudFront cache to clear
- Check ECS task logs for frontend route registration
- Verify templates directory exists in Docker image


