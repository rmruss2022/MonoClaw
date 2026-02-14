You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-050 - Build auth backend with JWT tokens
PRIORITY: Critical (P0) - blocks 10 downstream auth and user tasks
ESTIMATED HOURS: 5

DESCRIPTION:
Implement a complete authentication backend with JWT tokens for the Ora AI app.

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/
TECH STACK: Node.js + TypeScript + PostgreSQL
EXISTING STRUCTURE:
- Server: src/server.ts
- Routes: src/routes/
- Controllers: src/controllers/
- Services: src/services/
- Models: src/models/
- Middleware: src/middleware/
- DB: src/db/
- Config: src/config/

ENDPOINTS TO IMPLEMENT:

1. **POST /auth/register**
   - Body: { email, password, name }
   - Hash password with bcrypt (10 rounds)
   - Create user in PostgreSQL
   - Return JWT access token (7-day expiry) + refresh token (30-day)
   - Validation: email format, password min 8 chars

2. **POST /auth/login**
   - Body: { email, password }
   - Verify credentials against stored hash
   - Return JWT access token + refresh token
   - Track last_login timestamp

3. **POST /auth/refresh**
   - Body: { refreshToken }
   - Validate refresh token
   - Return new access token + new refresh token
   - Invalidate old refresh token (rotation)

4. **POST /auth/forgot-password**
   - Body: { email }
   - Generate password reset token (1 hour expiry)
   - Return success (don't reveal if email exists)
   - Store reset token in DB

5. **POST /auth/reset-password**
   - Body: { token, newPassword }
   - Validate reset token
   - Update password hash
   - Invalidate all existing refresh tokens

6. **GET /auth/me** (protected)
   - Requires valid JWT in Authorization header
   - Returns current user profile

FILES TO CREATE/MODIFY:

1. **src/routes/auth.routes.ts** - Auth route definitions
2. **src/controllers/auth.controller.ts** - Request handling logic
3. **src/services/auth.service.ts** - Business logic (hashing, JWT, validation)
4. **src/middleware/auth.middleware.ts** - JWT verification middleware
5. **src/models/user.model.ts** - User model/queries
6. **src/db/migrations/001_create_users.sql** - Users table migration
7. **src/db/migrations/002_create_refresh_tokens.sql** - Refresh tokens table
8. **src/config/auth.config.ts** - JWT secret, expiry settings

DATABASE TABLES:

```sql
-- Users table
CREATE TABLE IF NOT EXISTS users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email VARCHAR(255) UNIQUE NOT NULL,
  password_hash VARCHAR(255) NOT NULL,
  name VARCHAR(255) NOT NULL,
  avatar_url TEXT,
  bio TEXT,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),
  last_login TIMESTAMPTZ,
  is_active BOOLEAN DEFAULT true,
  quiz_data JSONB
);

-- Refresh tokens
CREATE TABLE IF NOT EXISTS refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(255) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked_at TIMESTAMPTZ
);

-- Password reset tokens
CREATE TABLE IF NOT EXISTS password_reset_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token VARCHAR(255) UNIQUE NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);
```

SECURITY REQUIREMENTS:
- bcrypt for password hashing (cost factor 10)
- JWT signed with HS256, secret from environment variable
- Refresh token rotation (old token invalidated on use)
- Rate limiting on login (5 attempts per minute)
- Input validation and sanitization
- No password in JWT payload (only user id, email, name)

DEPENDENCIES TO INSTALL (check if already in package.json first):
- jsonwebtoken / @types/jsonwebtoken
- bcrypt / @types/bcrypt
- express-rate-limit (if not present)
- uuid (if not present)

STEPS:
1. Read existing package.json and server.ts to understand current setup
2. Read existing routes, controllers, services to understand patterns
3. Check what DB setup exists (postgres connection, existing tables)
4. Create migration files
5. Create auth config
6. Create user model
7. Create auth service
8. Create auth middleware
9. Create auth controller
10. Create auth routes
11. Register routes in server.ts
12. Test endpoints work (basic sanity check)

ACCEPTANCE CRITERIA:
- All 6 endpoints implemented and functional
- Passwords properly hashed with bcrypt
- JWT tokens properly signed and verified
- Refresh token rotation working
- Rate limiting on login endpoint
- Clean TypeScript types throughout
- Follows existing codebase patterns

WHEN COMPLETE, run these commands:
```bash
curl -X PATCH http://localhost:3001/api/tasks/ORA-050 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'
curl -X POST http://localhost:3001/api/activity -H "Content-Type: application/json" -d '{"project_id": 3, "task_id": "ORA-050", "agent_type": "backend-dev", "action": "completed", "details": "Auth backend built with JWT - register, login, refresh, forgot-password, reset-password, me endpoints"}'
```

START NOW.
