# ORA-024: Add inner thought vector generation

## Context
Ora AI behavior selection needs better context awareness. Currently uses direct user message embedding.

## Task
Before behavior selection, generate LLM "inner thought" about conversation state and embed it as additional vector.

## Implementation
Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/

1. Update behavior selection endpoint (likely `src/services/behaviors.service.ts`):
   - Before embedding user message, call LLM with system prompt:
     ```
     You are Ora's inner voice. Analyze this conversation state in 1-2 sentences:
     [last 3 messages context]
     
     Generate an inner thought about: user's emotional state, topic shifts, what they need.
     Example: "User seems anxious about work. Topic shifted from meditation to career stress."
     ```
   
2. Embed inner thought as additional vector:
   - Get embedding for inner thought text
   - Include in broadcast alongside user message embedding
   - Weight: 0.3 (vs 1.0 for user message)

3. Log inner thoughts for debugging (optional)

## Acceptance
- Inner thoughts generated before behavior selection
- Thoughts embedded and included in ranking
- Context-aware behavior selection improves

## Project
- Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/
