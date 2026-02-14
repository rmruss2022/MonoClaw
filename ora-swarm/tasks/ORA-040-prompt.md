You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-040 - Build threaded discussion system backend
PRIORITY: High (P1)
ESTIMATED HOURS: 5

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/

DELIVERABLES:
1. Database migration for threaded discussions:
   - comments table (id, post_id, parent_comment_id, user_id, body, created_at, updated_at)
   - comment_reactions table (id, comment_id, user_id, reaction_type, created_at)
   - Recursive CTE queries for nested threads

2. API endpoints:
   - GET /api/posts/:id/comments - Get threaded comments for a post
   - POST /api/posts/:id/comments - Add comment to a post
   - POST /api/comments/:id/reply - Reply to a comment (nested)
   - POST /api/comments/:id/react - React to a comment (like, support, insightful)
   - DELETE /api/comments/:id - Soft delete a comment
   - GET /api/comments/:id/thread - Get full thread from a comment

3. Comment service at src/services/comment.service.ts
4. Comment controller at src/controllers/comment.controller.ts
5. Comment routes at src/routes/comment.routes.ts

Read existing code patterns. Follow TypeScript conventions. Auth middleware for protected routes.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-040 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
