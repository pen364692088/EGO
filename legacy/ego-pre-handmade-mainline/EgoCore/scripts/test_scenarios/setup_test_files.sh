#!/bin/bash
# Setup test files for Telegram E2E testing
# Run this script to create the necessary test files

set -e

echo "Setting up test files for Telegram E2E testing..."

# Create test directories
mkdir -p /tmp/e2e_test

# Create file for file_read success test
echo "Hello E2E Test
This is a test file for Proto-Self Kernel E2E validation.
Created: $(date)
Purpose: Verify file_read cycle creation
" > /tmp/e2e_test_hello.txt

# Create file for cycle strengthen test
echo "Cycle Strengthen Test File
This file is used to test cycle consolidation.
Multiple similar file read requests should hit the same cycle." > /tmp/e2e_cycle_test.txt

echo "Test files created:"
echo "  - /tmp/e2e_test_hello.txt (for file_read success test)"
echo "  - /tmp/e2e_cycle_test.txt (for cycle strengthen test)"
echo ""
echo "Files NOT created (for failure testing):"
echo "  - /tmp/e2e_not_exist_xyz_12345.txt (should NOT exist for external_failure test)"
