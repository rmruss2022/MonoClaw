#!/bin/bash
# This inserts profile application code into create-agent.sh

# After line 217 (SETUP_EOF), insert:
PROFILE_CODE='
# Apply profile if specified
if [ -n "$PROFILE_PATH" ]; then
  echo -e "${GREEN}Applying profile: $PROFILE_NAME${NC}"
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
  "$SCRIPT_DIR/apply-profile.sh" "$AGENT_NAME" "$PROFILE_PATH"
fi
'

# Use sed to insert after SETUP_EOF
sed -i.bak '/^SETUP_EOF$/a\
\
# Apply profile if specified\
if [ -n "$PROFILE_PATH" ]; then\
  echo -e "${GREEN}Applying profile: $PROFILE_NAME${NC}"\
  SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\
  "$SCRIPT_DIR/apply-profile.sh" "$AGENT_NAME" "$PROFILE_PATH"\
fi
' ~/.openclaw/workspace/vm-agent-system/provisioning/create-agent.sh

echo "Patched create-agent.sh to support profiles"
