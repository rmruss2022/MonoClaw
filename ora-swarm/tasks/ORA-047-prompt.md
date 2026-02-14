You are a Designer-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-047 - Design auth screens (sign-up, sign-in, forgot password)
PRIORITY: Critical (P0) - blocks auth frontend implementation
ESTIMATED HOURS: 4

APP ROOT: /Users/matthew/Desktop/Feb26/ora-ai/
BRAND ASSETS: /Users/matthew/Desktop/Feb26/Ora 2/
BRAND AUDIT: /Users/matthew/Desktop/Feb26/ora-ai/docs/design/brand-audit.md

DELIVERABLES:
1. Design spec at /Users/matthew/Desktop/Feb26/ora-ai/docs/design/auth-screens-spec.md:
   - Sign Up screen (name, email, password, confirm password, sign up button, "already have account?" link)
   - Sign In screen (email, password, sign in button, "forgot password?" link, "create account" link)
   - Forgot Password screen (email input, reset button, back to sign in)
   - All with Ora brand colors, fonts, spacing
   - Include form validation states (error, focus, success)

2. Implement React Native screens:
   - /Users/matthew/Desktop/Feb26/ora-ai/src/screens/auth/SignUpScreen.tsx
   - /Users/matthew/Desktop/Feb26/ora-ai/src/screens/auth/SignInScreen.tsx
   - /Users/matthew/Desktop/Feb26/ora-ai/src/screens/auth/ForgotPasswordScreen.tsx
   - Clean, modern design with proper keyboard handling
   - Form validation with error messages
   - Loading states for API calls

Read existing theme and patterns first. Use brand colors from the brand audit.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-047 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
