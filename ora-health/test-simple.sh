#!/bin/bash

# Get auth token by signing in
TOKEN=$(curl -s -X POST http://localhost:3000/auth/signin \
  -H "Content-Type: application/json" \
  -d '{"email":"test@shadow-ai.com","password":"testpassword"}' \
  | jq -r '.token')

echo "Token: $TOKEN"
echo ""
echo "Sending test message..."
echo ""

# Send a message that should trigger Difficult Emotion Processing
curl -X POST http://localhost:3000/chat/messages \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"content":"I am feeling really overwhelmed and cant cope", "behaviorId":"free-form-chat"}' \
  | jq '.'
