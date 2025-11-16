# Terraform Fixes for CD Pipeline Issues

This document describes the fixes for two common Terraform issues in the CD pipeline:

## Issue 1: Terraform Plugin Cache Directory Does Not Exist

**Problem:** 
```
The specified plugin cache dir ~/.terraform.d/plugin-cache cannot be opened: stat ~/.terraform.d/plugin-cache: no such file or directory
```

**Solution:**
The `.terraformrc` file in this directory configures Terraform to use the plugin cache directory. However, for this to work automatically, you need to either:

1. **Set `TF_CLI_CONFIG_FILE` environment variable** (recommended for CI):
   ```bash
   export TF_CLI_CONFIG_FILE="$(pwd)/.terraformrc"
   ```

2. **Or copy `.terraformrc` to home directory** (for local use):
   ```bash
   cp .terraformrc ~/.terraformrc
   ```

3. **Or use the setup script** before running Terraform:
   ```bash
   source ./setup-terraform-env.sh
   ```

The setup script (`setup-terraform-env.sh`) ensures the directory exists and sets the environment variable.

## Issue 2: Terraform Import Fails - Resources Already in State

**Problem:**
```
Error: resource already managed: module.ddb.aws_dynamodb_table.this["artifacts"]. To import to this address you must first remove the existing object from the state.
```

**Solution:**
Use the improved import script (`import-tables.sh`) which:
- Checks if resources are already in state before importing
- Handles the "already in state" error gracefully
- Uses better pattern matching for resource addresses with brackets
- Provides clear feedback on what's happening

**Usage:**
```bash
cd infra/envs/dev
./import-tables.sh
```

The script automatically:
- Creates the plugin cache directory if needed
- Sets required environment variables
- Imports only tables that aren't already in state
- Skips tables that are already managed

## Integration with CD Workflow

To use these fixes in the CD workflow without modifying the workflow file, you can:

1. **For the plugin cache issue:** The workflow already creates the directory, but you can ensure it's set up by running:
   ```bash
   mkdir -p ~/.terraform.d/plugin-cache
   export TF_PLUGIN_CACHE_DIR=~/.terraform.d/plugin-cache
   ```
   (This is already done in the workflow, but the `.terraformrc` file provides a backup)

2. **For the import issue:** Replace the inline bash import logic with a call to the script:
   ```bash
   ./import-tables.sh
   ```
   However, this requires modifying the workflow to call the script instead of using inline bash.

## Alternative: Manual Fixes

If you cannot modify the workflow, you can manually:

1. **Remove resources from state before re-importing:**
   ```bash
   terraform state rm 'module.ddb.aws_dynamodb_table.this["artifacts"]'
   terraform import 'module.ddb.aws_dynamodb_table.this["artifacts"]' artifacts
   ```

2. **Or skip imports if resources are already managed:**
   The improved import script handles this automatically.

