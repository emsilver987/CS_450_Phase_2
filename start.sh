#!/bin/bash
set -e

# Log startup information
echo "=== Starting validator service ===" >&2
echo "Python version: $(python --version)" >&2
echo "Working directory: $(pwd)" >&2
echo "Python path: $PYTHONPATH" >&2
echo "" >&2
echo "=== Environment variables ===" >&2
env | grep -E "(AWS_|PORT|RDS_|STORAGE_|DDB_|ARTIFACTS_|PYTHON_|JWT_|GITHUB_|CLOUDWATCH_)" | sort >&2
echo "" >&2

# Test if we can import the application
echo "=== Testing application import ===" >&2
python -c "
import sys
import traceback
try:
    print('Importing src.entrypoint...', file=sys.stderr)
    from src.entrypoint import app
    print('SUCCESS: Application imported successfully', file=sys.stderr)
    print(f'App type: {type(app)}', file=sys.stderr)
except ImportError as e:
    print(f'ERROR: Import error: {e}', file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
except Exception as e:
    print(f'ERROR: Failed to import application: {e}', file=sys.stderr)
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
" || {
    echo "ERROR: Application import failed - see above for details" >&2
    exit 1
}

# Start uvicorn with error handling
echo "" >&2
echo "=== Starting uvicorn server ===" >&2
exec uvicorn src.entrypoint:app \
    --host 0.0.0.0 \
    --port 3000 \
    --log-level info \
    --access-log \
    --no-use-colors \
    2>&1

