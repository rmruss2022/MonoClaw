# ORA-044: Add anonymous posting option

## Context
Community forum needs anonymous posting for sensitive topics.

## Task
Allow users to post anonymously with toggle in CreatePost screen.

## Backend
Files: /Users/matthew/Desktop/Feb26/ora-ai-api/

1. Update Post model schema:
   - Add `isAnonymous: boolean` field
   - Keep `userId` for moderation but hide from API response when anonymous

2. Update API endpoints:
   - POST /posts - Accept `isAnonymous` flag
   - GET /posts - Return "Anonymous Supporter" + random animal avatar when anonymous
   - Store mapping of userId → animalId in session or database for consistency

## Frontend
Files: /Users/matthew/Desktop/Feb26/ora-ai/

1. Update `CreatePostScreen.tsx`:
   - Add toggle: "Post as Anonymous"
   - Default: false
   - Send `isAnonymous` to API

2. Update `PostCard.tsx`:
   - Show "Anonymous Supporter" + animal emoji when anonymous
   - Hide real user name/avatar

## Animal avatars
Use simple emoji: 🐼🦊🐨🦋🐰🐸 (6 options, assign by userId % 6)

## Acceptance
- Users can toggle anonymous posting
- Anonymous posts show generic identity
- Real userId stored for moderation

## Projects
- App: /Users/matthew/Desktop/Feb26/ora-ai/
- Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/
