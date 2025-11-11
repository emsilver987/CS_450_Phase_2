# Docker Setup Guide

## Quick Start

### Option 1: Using Docker Compose (Recommended)

```powershell
# Build and run
.\build_and_run_docker.ps1

# Or manually:
docker-compose up --build
```

### Option 2: Manual Docker Build

```powershell
# Build the image
docker build -t validator-api:latest .

# Run the container
docker run -p 3000:3000 `
  -e AWS_REGION=us-east-1 `
  -e AWS_ACCOUNT_ID=838693051036 `
  -e S3_ACCESS_POINT_NAME=cs450-s3 `
  -v "$env:USERPROFILE\.aws:/root/.aws:ro" `
  validator-api:latest
```

## AWS Credentials

The container needs AWS credentials to access S3 and DynamoDB. You have two options:

### Option 1: Mount AWS Credentials (Recommended for Local Development)

The container will automatically use your local AWS credentials if they exist at `~/.aws/`.

### Option 2: Environment Variables

Set AWS credentials as environment variables:
```powershell
docker run -p 3000:3000 `
  -e AWS_REGION=us-east-1 `
  -e AWS_ACCOUNT_ID=838693051036 `
  -e S3_ACCESS_POINT_NAME=cs450-s3 `
  -e AWS_ACCESS_KEY_ID=your_access_key `
  -e AWS_SECRET_ACCESS_KEY=your_secret_key `
  validator-api:latest
```

## Access the Application

Once the container is running:
- **Frontend:** http://localhost:3000
- **API Docs:** http://localhost:3000/docs
- **Health Check:** http://localhost:3000/health

## Troubleshooting

### Container can't access AWS
- Verify AWS credentials are configured: `aws sts get-caller-identity`
- Check that credentials are mounted: `docker exec <container_id> ls -la /root/.aws`
- Verify environment variables are set: `docker exec <container_id> env | grep AWS`

### Port already in use
- Stop any existing servers on port 3000
- Or change the port mapping: `-p 3001:3000`

### Build fails
- Ensure Docker Desktop is running
- Check that `requirements.txt` is valid
- Try: `docker system prune -a` to clear cache


