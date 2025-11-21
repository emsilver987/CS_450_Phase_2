#!/bin/bash
# Import existing S3 Access Point to fix 409 conflict

set -e

echo "Importing S3 Access Point..."
terraform import module.s3.aws_s3_access_point.main pkg-artifacts:cs450-s3

echo "Import complete. Run terraform plan to verify."
