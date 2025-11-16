#!/usr/bin/env bash
# Setup script to ensure Terraform environment is properly configured
# This script ensures the plugin cache directory exists and sets up the environment

set -euo pipefail

# Ensure plugin cache directory exists
mkdir -p ~/.terraform.d/plugin-cache

# Export environment variables
export TF_PLUGIN_CACHE_DIR="${TF_PLUGIN_CACHE_DIR:-~/.terraform.d/plugin-cache}"

echo "✓ Terraform plugin cache directory: $TF_PLUGIN_CACHE_DIR"
echo "✓ Directory exists: $(test -d ~/.terraform.d/plugin-cache && echo 'yes' || echo 'no')"

