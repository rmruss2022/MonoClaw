You are an iOS-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-051 - Implement secure token storage and auth context
PRIORITY: Critical (P0) - blocks all auth-gated features
ESTIMATED HOURS: 5

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/

Auth backend is COMPLETE at:
- /Users/matthew/Desktop/Feb26/ora-ai-api/src/services/auth.service.ts
- /Users/matthew/Desktop/Feb26/ora-ai-api/src/controllers/auth.controller.ts
- /Users/matthew/Desktop/Feb26/ora-ai-api/src/routes/auth.routes.ts
- /Users/matthew/Desktop/Feb26/ora-ai-api/src/middleware/auth.middleware.ts

DELIVERABLES:
1. Create /Users/matthew/Desktop/Feb26/ora-ai/src/context/AuthContext.tsx:
   - React Context with login, register, logout, refreshToken functions
   - Auto-refresh on app launch
   - Loading state for auth check

2. Create /Users/matthew/Desktop/Feb26/ora-ai/src/services/secureStorage.ts:
   - Use expo-secure-store for JWT + refresh token
   - Fallback to AsyncStorage for non-sensitive data
   - Token refresh logic

3. Create /Users/matthew/Desktop/Feb26/ora-ai/src/services/api.ts:
   - Axios/fetch wrapper with auth headers
   - Auto-retry on 401 with token refresh
   - Base URL configuration

4. Update navigation to handle auth state (logged in vs logged out flow)

Read existing code first, follow patterns. Auth API endpoints: POST /auth/register, /auth/login, /auth/refresh, /auth/me

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-051 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
