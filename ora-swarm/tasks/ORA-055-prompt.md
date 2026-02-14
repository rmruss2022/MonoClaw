You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-055 - Save quiz responses and build user profile
PRIORITY: Critical (P0)
ESTIMATED HOURS: 4

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/

Quiz questions are COMPLETE at: /Users/matthew/Desktop/Feb26/ora-ai/docs/content/intake-quiz.md
Quiz schema at: /Users/matthew/Desktop/Feb26/ora-ai/docs/content/quiz-data-schema.json
Auth backend is COMPLETE with user model at: /Users/matthew/Desktop/Feb26/ora-ai-api/src/services/auth.service.ts

DELIVERABLES:
1. Create POST /api/users/:id/quiz endpoint to save quiz responses
2. Create GET /api/users/:id/profile to get user profile with quiz data
3. Create PATCH /api/users/:id/profile to update profile
4. Database migration for user_profiles table with quiz_responses JSONB column
5. Service to compute personalization settings from quiz responses:
   - Map Q1 responses to suggested behaviors
   - Map Q5 response to notification frequency
   - Map Q6 response to preferred check-in time
   - Map Q8 response to initial content difficulty level
6. Create user profile model/service at src/services/profile.service.ts

Read existing code patterns first. Follow TypeScript conventions.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-055 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
