# ORA-042: Add reaction system to forum posts and comments

## Context
Community forum needs engagement features. Users want to react with emoji instead of typing responses.

## Task
Implement emoji reaction system for posts and comments (backend + frontend).

## Backend (Node.js + Prisma)
Files: /Users/matthew/Desktop/Feb26/ora-ai-api/

1. Create `prisma/schema.prisma` table:
```prisma
model Reaction {
  id          String   @id @default(uuid())
  userId      String
  targetId    String   // post or comment id
  targetType  String   // "post" or "comment"
  emoji       String   // "❤️", "👍", "🤗", "💡", "🔥"
  createdAt   DateTime @default(now())
  
  @@unique([userId, targetId, emoji])
  @@index([targetId, targetType])
}
```

2. Create API endpoints in `src/routes/reactions.ts`:
   - POST /reactions - Add reaction
   - DELETE /reactions/:id - Remove reaction
   - GET /reactions/:targetId - Get reactions for target
   - Include aggregated counts

3. Run migration: `npx prisma migrate dev --name add-reactions`

## Frontend (React Native)
Files: /Users/matthew/Desktop/Feb26/ora-ai/

1. Create `src/components/ReactionBar.tsx`:
   - Show emoji counts below posts/comments
   - Tap to add/remove reaction
   - Long-press for emoji picker (5 emojis)
   - Highlight user's reactions

2. Update PostCard.tsx and CommentCard.tsx:
   - Import and render ReactionBar
   - Pass post/comment id and type

## Acceptance
- Users can react with 5 emoji types
- Reactions persist and aggregate correctly
- Long-press shows picker, tap toggles reaction
- UI updates optimistically

## Project paths
- App: /Users/matthew/Desktop/Feb26/ora-ai/
- Backend: /Users/matthew/Desktop/Feb26/ora-ai-api/
