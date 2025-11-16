#!/usr/bin/env bash
# Improved import logic that can replace the inline bash in the CD workflow
# This handles both the plugin cache directory and resources already in state

# Ensure plugin cache directory exists before any Terraform command
mkdir -p ~/.terraform.d/plugin-cache
export TF_PLUGIN_CACHE_DIR=~/.terraform.d/plugin-cache

# Import existing tables only if not already in state
# Improved check that handles resources already in state
import_table() {
    local resource_address="$1"
    local table_name="$2"
    
    # Get state list (suppress errors if state doesn't exist yet)
    local state_list
    state_list=$(terraform state list 2>/dev/null || echo "")
    
    # Escape brackets for better pattern matching
    local escaped_address
    escaped_address=$(echo "${resource_address}" | sed 's/\[/\\[/g; s/\]/\\]/g')
    
    # Check if resource exists in state using multiple patterns
    if echo "$state_list" | grep -qE "^${escaped_address}$|^${resource_address}$"; then
        echo "Table ${table_name} already in state, skipping import"
        return 0
    fi
    
    # Try to import and capture output
    echo "Importing ${table_name}..."
    local import_output
    local import_exit_code
    
    import_output=$(terraform import \
        -var="aws_region=us-east-1" \
        -var="artifacts_bucket=pkg-artifacts" \
        "${resource_address}" \
        "${table_name}" 2>&1)
    import_exit_code=$?
    
    if [ $import_exit_code -eq 0 ]; then
        echo "Successfully imported ${table_name}"
        return 0
    elif echo "$import_output" | grep -qE "already in state|existing object from the state|Resource already managed"; then
        echo "Table ${table_name} already in state (detected from error message), skipping"
        return 0
    else
        echo "Failed to import ${table_name}: $import_output"
        return 1
    fi
}

# Import all tables
import_table 'module.ddb.aws_dynamodb_table.this["artifacts"]' artifacts || true
import_table 'module.ddb.aws_dynamodb_table.this["users"]' users || true
import_table 'module.ddb.aws_dynamodb_table.this["uploads"]' uploads || true
import_table 'module.ddb.aws_dynamodb_table.this["tokens"]' tokens || true
import_table 'module.ddb.aws_dynamodb_table.this["packages"]' packages || true
import_table 'module.ddb.aws_dynamodb_table.this["downloads"]' downloads || true

