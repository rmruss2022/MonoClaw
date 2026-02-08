# Shadow AI - Complete Project Overview

## Project Structure

You now have **TWO separate projects** for security reasons:

```
/Users/matthew/Desktop/Feb26/
├── shadow-ai/              # Mobile App (React Native)
│   └── NO credentials, only makes API calls
│
└── shadow-ai-api/          # Backend API (Node.js)
    └── Has AWS & OpenAI credentials (server-side only)
```

## Why Two Separate Projects?

**Security Best Practice:** Never put AWS credentials or API keys in a mobile app!

- **Mobile apps can be decompiled** → credentials would be exposed
- **Backend API is secure** → credentials stay on server, never in app code

## 1. Mobile App (shadow-ai)

### Location
```
/Users/matthew/Desktop/Feb26/shadow-ai/
```

### What it does
- React Native app with Expo
- Chat interface for users
- Makes HTTP requests to backend API
- Stores JWT auth token locally (encrypted by OS)

### What it DOES NOT have
- ❌ AWS credentials
- ❌ OpenAI API keys
- ❌ Database connections
- ❌ Any sensitive credentials

### Key Files
```
shadow-ai/
├── src/
│   ├── services/api/      # HTTP API client (calls backend)
│   ├── services/storage/  # Local storage only (AsyncStorage)
│   ├── components/        # React components
│   ├── screens/           # App screens
│   ├── types/            # TypeScript types
│   └── config/api.ts      # API URL configuration
├── docs/context/          # Full documentation
│   ├── CLAUDE.md
│   ├── BEHAVIORS.md
│   ├── ARCHITECTURE.md
│   ├── TESTING.md
│   └── COMMUNITY.md
└── SECURITY.md            # Security architecture
```

### Run Mobile App
```bash
cd shadow-ai
npm start         # Start Expo
npm run ios       # Run on iOS
npm run android   # Run on Android
npm test          # Run tests
```

### Configuration
```bash
# shadow-ai/.env
API_BASE_URL=http://localhost:3000  # Points to backend API
```

## 2. Backend API (shadow-ai-api)

### Location
```
/Users/matthew/Desktop/Feb26/shadow-ai-api/
```

### What it does
- Node.js/Express REST API
- Handles authentication (JWT)
- Calls OpenAI API for chat
- Manages AWS DynamoDB database
- Validates all requests
- Rate limiting and security

### What it HAS (securely)
- ✅ AWS credentials (in .env, never committed)
- ✅ OpenAI API key (in .env, never committed)
- ✅ JWT secret for authentication
- ✅ Full database access

### Key Files
```
shadow-ai-api/
├── src/
│   ├── config/            # AWS & OpenAI setup
│   ├── controllers/       # Request handlers
│   ├── services/          # Business logic
│   ├── routes/            # API endpoints
│   ├── middleware/        # Auth middleware
│   └── server.ts          # Express app
├── .env.example           # Template (fill this out)
├── .env                   # Your credentials (NEVER commit!)
└── README.md              # API documentation
```

### Run Backend API
```bash
cd shadow-ai-api
npm install
cp .env.example .env      # Create your .env file
# Edit .env with your credentials
npm run dev               # Start development server
```

### Configuration
```bash
# shadow-ai-api/.env
PORT=3000
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_REGION=us-east-1
OPENAI_API_KEY=sk-your_key_here
JWT_SECRET=your_random_secret_string
```

## How They Work Together

### Architecture Flow

```
User interacts with Mobile App
        ↓
Mobile App makes HTTP request (with JWT token)
        ↓
Backend API receives request
        ↓
Backend validates JWT token
        ↓
Backend calls OpenAI API (server-side)
        ↓
Backend saves to DynamoDB (server-side)
        ↓
Backend returns response to Mobile App
        ↓
Mobile App displays to user
```

### Example: Sending a Chat Message

**Mobile App (shadow-ai):**
```typescript
// src/services/api/chatAPI.ts
const response = await apiClient.post('/chat/messages', {
  content: 'I want to journal',
  behaviorId: 'journal-prompt'
});
// apiClient adds: Authorization: Bearer <jwt-token>
```

**Backend API (shadow-ai-api):**
```typescript
// Receives request
// Validates JWT token
// Calls OpenAI with server-side API key
// Saves to DynamoDB with server-side credentials
// Returns AI response to mobile app
```

## AWS Setup Required

### DynamoDB Tables to Create

1. **shadow-ai-users**
   - Partition Key: `id` (String)
   - GSI: `email-index` with `email` as partition key

2. **shadow-ai-journal-entries**
   - Partition Key: `userId` (String)
   - Sort Key: `id` (String)

3. **shadow-ai-chat-messages**
   - Partition Key: `userId` (String)
   - Sort Key: `timestamp` (String)

4. **shadow-ai-community-posts**
   - Partition Key: `id` (String)
   - GSI: `createdAt-index` with `createdAt` as partition key

5. **shadow-ai-community-comments**
   - Partition Key: `postId` (String)
   - Sort Key: `id` (String)

## Development Workflow

### Step 1: Start Backend API
```bash
cd shadow-ai-api
npm run dev
# API running on http://localhost:3000
```

### Step 2: Configure Mobile App
```bash
cd shadow-ai
# Edit .env
API_BASE_URL=http://localhost:3000
```

### Step 3: Start Mobile App
```bash
cd shadow-ai
npm start
# Choose iOS, Android, or Web
```

### Step 4: Test
```bash
# Mobile app calls http://localhost:3000/auth/signup
# Backend creates user in DynamoDB
# Backend returns JWT token
# Mobile app stores token
# Mobile app makes authenticated requests
```

## Security Checklist

### Mobile App (shadow-ai)
- ✅ No AWS credentials in code
- ✅ No OpenAI keys in code
- ✅ Only stores JWT token
- ✅ All requests over HTTPS (production)
- ✅ No sensitive data hardcoded

### Backend API (shadow-ai-api)
- ✅ Credentials in .env (not committed)
- ✅ .env in .gitignore
- ✅ JWT authentication required
- ✅ Password hashing with bcrypt
- ✅ CORS configured
- ✅ Input validation

## Next Steps

### 1. Set Up Backend
1. Create AWS account and get credentials
2. Get OpenAI API key
3. Fill out `shadow-ai-api/.env`
4. Create DynamoDB tables
5. Run `npm run dev` in shadow-ai-api

### 2. Configure Mobile App
1. Update `shadow-ai/.env` with backend URL
2. Run `npm start` in shadow-ai
3. Test authentication flow

### 3. Start Building Features
1. Follow TDD approach (see TESTING.md)
2. Implement behaviors (see BEHAVIORS.md)
3. Build UI components
4. Test with backend API

## Documentation

### Mobile App Docs
- `shadow-ai/docs/context/CLAUDE.md` - Project overview
- `shadow-ai/docs/context/BEHAVIORS.md` - AI behaviors
- `shadow-ai/docs/context/ARCHITECTURE.md` - System design
- `shadow-ai/docs/context/TESTING.md` - TDD guidelines
- `shadow-ai/SECURITY.md` - Security architecture

### Backend API Docs
- `shadow-ai-api/README.md` - API documentation
- `shadow-ai-api/.env.example` - Configuration template

## Quick Reference

### Mobile App Commands
```bash
cd shadow-ai
npm start         # Start Expo
npm run ios       # iOS simulator
npm run android   # Android emulator
npm test          # Run tests
npm run test:coverage  # Coverage report
```

### Backend API Commands
```bash
cd shadow-ai-api
npm run dev       # Development server
npm run build     # Build TypeScript
npm start         # Production server
```

### API Endpoints
```
POST   /auth/signup              # Create account
POST   /auth/signin              # Sign in
POST   /chat/messages            # Send chat message
GET    /chat/history             # Get chat history
POST   /journal/entries          # Create journal entry
GET    /journal/entries          # Get entries
GET    /health                   # Check API status
```

## Support

- Review `shadow-ai/docs/context/` for detailed documentation
- Check `shadow-ai/SECURITY.md` for security guidelines
- See `shadow-ai-api/README.md` for backend API details

---

**Status:** ✅ Both projects set up and ready for development

**Security:** ✅ Proper separation of concerns - credentials only in backend

**Next:** Set up AWS, configure environment variables, start backend API
