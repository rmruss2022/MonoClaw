#!/bin/bash
# Apply profile configuration to an agent VM
# Usage: apply-profile.sh <vm-name> <profile-path>

set -e

VM_NAME="$1"
PROFILE_PATH="$2"

if [ -z "$VM_NAME" ] || [ -z "$PROFILE_PATH" ]; then
  echo "Usage: $0 <vm-name> <profile-path>"
  exit 1
fi

if [ ! -f "$PROFILE_PATH" ]; then
  echo "Error: Profile file not found: $PROFILE_PATH"
  exit 1
fi

echo "Applying profile to VM: $VM_NAME"

# Extract profile data
PROFILE_NAME=$(jq -r '.name' "$PROFILE_PATH")
echo "Profile: $PROFILE_NAME"

# Install system packages
PACKAGES=$(jq -r '.packages[]?' "$PROFILE_PATH" 2>/dev/null || echo "")
if [ -n "$PACKAGES" ]; then
  echo "Installing packages..."
  for pkg in $PACKAGES; do
    echo "  - $pkg"
    multipass exec "$VM_NAME" -- sudo apt-get install -y "$pkg" || true
  done
fi

# Create files
FILES_COUNT=$(jq '.files | length' "$PROFILE_PATH" 2>/dev/null || echo "0")
if [ "$FILES_COUNT" -gt 0 ]; then
  echo "Creating files..."
  for i in $(seq 0 $((FILES_COUNT - 1))); do
    FILE_PATH=$(jq -r ".files[$i].path" "$PROFILE_PATH")
    FILE_CONTENT=$(jq -r ".files[$i].content" "$PROFILE_PATH")
    
    echo "  - $FILE_PATH"
    echo "$FILE_CONTENT" | multipass exec "$VM_NAME" -- tee "$FILE_PATH" > /dev/null
  done
fi

# Set environment variables (add to .bashrc)
ENV_VARS=$(jq -r '.environment | to_entries[]? | "\(.key)=\(.value)"' "$PROFILE_PATH" 2>/dev/null || echo "")
if [ -n "$ENV_VARS" ]; then
  echo "Setting environment variables..."
  while IFS= read -r env_var; do
    echo "  - $env_var"
    multipass exec "$VM_NAME" -- bash -c "echo 'export $env_var' >> ~/.bashrc"
  done <<< "$ENV_VARS"
fi

# Run setup tasks
TASKS_COUNT=$(jq '.setup_tasks | length' "$PROFILE_PATH" 2>/dev/null || echo "0")
if [ "$TASKS_COUNT" -gt 0 ]; then
  echo "Running setup tasks..."
  for i in $(seq 0 $((TASKS_COUNT - 1))); do
    TASK_CMD=$(jq -r ".setup_tasks[$i].command" "$PROFILE_PATH")
    TASK_DESC=$(jq -r ".setup_tasks[$i].description" "$PROFILE_PATH")
    
    echo "  - $TASK_DESC"
    multipass exec "$VM_NAME" -- bash -c "$TASK_CMD" || echo "    (task failed, continuing...)"
  done
fi

echo "Profile applied successfully!"
