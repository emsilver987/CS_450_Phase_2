#!/bin/bash
# Script to import existing AWS resources into Terraform state
# Run this from the infra/envs/dev directory

set -e

echo "🚀 Starting Terraform resource import process..."
echo ""

# Set variables (adjust if needed)
AWS_ACCOUNT_ID="${AWS_ACCOUNT_ID:-838693051036}"
AWS_REGION="${AWS_REGION:-us-east-1}"
ARTIFACTS_BUCKET="${ARTIFACTS_BUCKET:-pkg-artifacts}"

echo "Using AWS Account ID: $AWS_ACCOUNT_ID"
echo "Using AWS Region: $AWS_REGION"
echo "Using Artifacts Bucket: $ARTIFACTS_BUCKET"
echo ""

# Initialize Terraform
echo "📦 Initializing Terraform..."
terraform init

echo ""
echo "📥 Importing existing resources..."
echo ""

# 1. Import Config module resources
echo "1️⃣  Importing Config module resources..."
CONFIG_BUCKET_NAME="${ARTIFACTS_BUCKET}-config-${AWS_ACCOUNT_ID}"
if terraform import module.config.aws_s3_bucket.config_snapshots "$CONFIG_BUCKET_NAME" 2>/dev/null; then
    echo "   ✅ Imported Config S3 bucket: $CONFIG_BUCKET_NAME"
else
    echo "   ⚠️  Config S3 bucket may not exist or already imported: $CONFIG_BUCKET_NAME"
fi

if terraform import module.config.aws_iam_role.config_role "aws-config-role" 2>/dev/null; then
    echo "   ✅ Imported Config IAM role: aws-config-role"
else
    echo "   ⚠️  Config IAM role may not exist or already imported: aws-config-role"
fi

# 2. Import Monitoring module resources
echo ""
echo "2️⃣  Importing Monitoring module resources..."
CLOUDTRAIL_BUCKET_NAME="${ARTIFACTS_BUCKET}-cloudtrail-logs-${AWS_ACCOUNT_ID}"
if terraform import module.monitoring.aws_s3_bucket.cloudtrail_logs "$CLOUDTRAIL_BUCKET_NAME" 2>/dev/null; then
    echo "   ✅ Imported CloudTrail S3 bucket: $CLOUDTRAIL_BUCKET_NAME"
else
    echo "   ⚠️  CloudTrail S3 bucket may not exist or already imported: $CLOUDTRAIL_BUCKET_NAME"
fi

if terraform import module.monitoring.aws_cloudwatch_log_group.cloudtrail_logs "/aws/cloudtrail/acme-audit-trail" 2>/dev/null; then
    echo "   ✅ Imported CloudWatch Log Group: /aws/cloudtrail/acme-audit-trail"
else
    echo "   ⚠️  CloudWatch Log Group may not exist or already imported"
fi

# 3. Import S3 module resources
echo ""
echo "3️⃣  Importing S3 module resources..."
if terraform import module.s3.aws_s3_bucket.artifacts "$ARTIFACTS_BUCKET" 2>/dev/null; then
    echo "   ✅ Imported S3 artifacts bucket: $ARTIFACTS_BUCKET"
else
    echo "   ⚠️  S3 artifacts bucket may not exist or already imported: $ARTIFACTS_BUCKET"
fi

echo ""
echo "✅ Import process completed!"
echo ""
echo "📋 Next steps:"
echo "   1. Run 'terraform plan' to see what changes Terraform wants to make"
echo "   2. Review the plan carefully"
echo "   3. Run 'terraform apply' to sync any configuration changes"
echo ""
echo "💡 Tip: If you see 'forces replacement' warnings, you may need to:"
echo "   - Adjust resource configurations to match existing resources"
echo "   - Or accept the replacement (be careful with production resources!)"

