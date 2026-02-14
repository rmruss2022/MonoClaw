You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-075 - Set up pgvector extension for vector storage
PRIORITY: Critical (P0) - blocks multi-vector chat system
ESTIMATED HOURS: 4

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/
ARCHITECTURE DOC (being created): /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/multi-vector-system.md
SCHEMA DOC (being created): /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/vector-schema.sql

DELIVERABLES:
1. Database migration to enable pgvector extension (CREATE EXTENSION IF NOT EXISTS vector)
2. Create vector storage tables per the architecture doc (read it first if it exists)
3. Create embedding service at src/services/embedding.service.ts:
   - OpenAI text-embedding-3-small API integration
   - Batch embedding generation
   - Caching layer for frequent queries
4. Create vector search service at src/services/vector-search.service.ts:
   - Cosine similarity search
   - HNSW index configuration
   - Top-K retrieval
5. Update docker-compose.yml to use pgvector-enabled PostgreSQL image
6. Create test script for vector operations

Read existing postgres setup and patterns first.

WHEN COMPLETE:
curl -X PATCH http://localhost:3001/api/tasks/ORA-075 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'

START NOW.
