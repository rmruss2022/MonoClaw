You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-026 - Design letters system data model and API
PRIORITY: Critical (P0) - blocks 10+ downstream letter feature tasks
ESTIMATED HOURS: 4

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/

DESCRIPTION:
Design and implement the complete data model and API for the Letters system - a daily inbox feature where users receive and send personal letters. Think of it like a private, intimate messaging system with an "envelope" metaphor.

DELIVERABLES:
1. Database migration at src/db/migrations/ for letters tables:
   - letters (id, sender_id, recipient_id, subject, body, is_ai_generated, sent_at, read_at, etc.)
   - letter_threads (id, letter_id, parent_letter_id for threading)
   - letter_templates (id, category, subject_template, body_template, for AI-generated letters)

2. API endpoints:
   - GET /api/letters/inbox - User's received letters (paginated)
   - GET /api/letters/sent - User's sent letters
   - GET /api/letters/:id - Read a specific letter
   - POST /api/letters - Send a new letter
   - POST /api/letters/:id/reply - Reply to a letter
   - PATCH /api/letters/:id/read - Mark as read
   - GET /api/letters/unread-count - Unread badge count

3. Letter service at src/services/letter.service.ts
4. Letter controller at src/controllers/letter.controller.ts
5. Letter routes at src/routes/letter.routes.ts
6. AI daily letter generator service (generates personalized motivational letters)

Read existing code patterns first. Follow TypeScript conventions. Auth middleware already exists.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-026 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
