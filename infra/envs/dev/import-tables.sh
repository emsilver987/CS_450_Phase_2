#!/usr/bin/env bash
# Script to import existing DynamoDB tables into Terraform state
# This script handles resources that are already in state gracefully

set -euo pipefail

# Ensure plugin cache directory exists
mkdir -p ~/.terraform.d/plugin-cache

# Set Terraform variables
export TF_VAR_aws_region="${TF_VAR_aws_region:-us-east-1}"
export TF_VAR_artifacts_bucket="${TF_VAR_artifacts_bucket:-pkg-artifacts}"
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-~/.terraform.d/plugin-cache}"

# Function to import a DynamoDB table
import_table() {
    local resource_address="$1"
    local table_name="$2"
    
    echo "Checking if ${table_name} is already in state..."
    
    # Get current state list and check if resource exists
    # Use a more robust check that handles brackets and escaping
    local state_list
    state_list=$(terraform state list 2>/dev/null || echo "")
    
    # Check if resource exists in state (handle both exact match and pattern match)
    if echo "$state_list" | grep -qE "^${resource_address}$|^${resource_address//\[/\\[}"; then
        echo "✓ Table ${table_name} already in state, skipping import"
        return 0
    fi
    
    # Try to import
    echo "Importing ${table_name}..."
    local import_output
    import_output=$(terraform import \
        -var="aws_region=${TF_VAR_aws_region}" \
        -var="artifacts_bucket=${TF_VAR_artifacts_bucket}" \
        "${resource_address}" \
        "${table_name}" 2>&1) || {
        # Check if the error is because resource is already in state
        if echo "$import_output" | grep -qE "already in state|existing object from the state|Resource already managed by Terraform"; then
            echo "✓ Table ${table_name} already in state (detected from error), skipping"
            return 0
        else
            echo "⚠ Failed to import ${table_name}: $import_output"
            return 1
        fi
    }
    
    echo "✓ Successfully imported ${table_name}"
    return 0
}

# Import all tables
echo "Starting DynamoDB table imports..."
echo ""

import_table 'module.ddb.aws_dynamodb_table.this["artifacts"]' artifacts || true
import_table 'module.ddb.aws_dynamodb_table.this["users"]' users || true
import_table 'module.ddb.aws_dynamodb_table.this["uploads"]' uploads || true
import_table 'module.ddb.aws_dynamodb_table.this["tokens"]' tokens || true
import_table 'module.ddb.aws_dynamodb_table.this["packages"]' packages || true
import_table 'module.ddb.aws_dynamodb_table.this["downloads"]' downloads || true

echo ""
echo "Import process completed."

