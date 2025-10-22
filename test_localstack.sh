
echo "Testing LocalStack + FastAPI TestClient Integration"

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "Docker not found. Please install Docker to run this test."
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo " Docker daemon not running. Please start Docker to run this test."
    exit 1
fi

# Clean up any existing LocalStack container
echo "Cleaning up existing LocalStack..."
docker rm -f localstack 2>/dev/null || true

# Start LocalStack
echo "Starting LocalStack..."
docker run -d --name localstack \
  -p 4566:4566 \
  -e SERVICES="s3,dynamodb" \
  localstack/localstack:latest

# Wait for LocalStack to be ready
echo "Waiting for LocalStack to be ready..."
for i in {1..40}; do
  if curl -s http://localhost:4566/health | grep -q '"initialized": true'; then
    echo "LocalStack ready!"
    break
  fi
  echo "Attempt $i/40..."
  sleep 1
done

# Set environment variables
echo "Setting up environment..."
export AWS_ENDPOINT_URL=http://localhost:4566
export AWS_DEFAULT_REGION=us-east-1
export AWS_ACCESS_KEY_ID=test
export AWS_SECRET_ACCESS_KEY=test
export ARTIFACTS_BUCKET=pkg-artifacts
export DDB_TABLE_PACKAGES=packages
export DDB_TABLE_UPLOADS=uploads
export DDB_TABLE_USERS=users
export DDB_TABLE_TOKENS=tokens
export DDB_TABLE_DOWNLOADS=downloads
export PYTHONPATH=src:$PYTHONPATH

# Setup LocalStack resources
echo "Setting up LocalStack resources..."
python -c "from tests.fixtures.localstack_setup import setup_localstack_resources; setup_localstack_resources()"

# Run tests with integration
echo "Running tests with integration..."
pytest -v --cov=src --run-integration

# Clean up
echo "Cleaning up LocalStack..."
docker rm -f localstack

echo "Test complete!"
