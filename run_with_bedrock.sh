#!/bin/bash

# 1. Install boto3 if missing
echo "📦 Checking dependencies..."
pip install boto3 > /dev/null 2>&1
if [ $? -eq 0 ]; then
    echo "✅ boto3 installed"
else
    echo "❌ Failed to install boto3. Please run 'pip install boto3' manually."
    exit 1
fi

# 2. Set AWS Credentials
# REPLACE THESE VALUES WITH YOUR ACTUAL CREDENTIALS
# OR set them in your environment before running this script
export AWS_ACCESS_KEY_ID="YOUR_ACCESS_KEY_HERE"
export AWS_SECRET_ACCESS_KEY="YOUR_SECRET_KEY_HERE"
export AWS_REGION="us-east-1"  # Ensure this region supports Claude 3 Haiku

# 3. Enable LLM Mode
export ENABLE_LLM=true

echo "========================================================"
echo "🚀 STARTING BEDROCK VERIFICATION"
echo "========================================================"
echo "Region: $AWS_REGION"
echo "LLM Enabled: $ENABLE_LLM"
echo "========================================================"

# 4. Run Verification
python verify_bedrock.py
