You are a Backend-Dev-Agent working on the Ora AI App Store Polish project (Project ID: 3).

TASK: ORA-011 - Design multi-vector embedding architecture 🔴 CRITICAL
PRIORITY: Critical (P0) - blocks 14 downstream chat system tasks
ESTIMATED HOURS: 6

DESCRIPTION:
Design the complete architecture for an embedding-based behavior detection system that replaces the current keyword-matching approach. This is the most critical task in the project as it blocks all multi-vector chat system work.

CURRENT SYSTEM: /Users/matthew/Desktop/Feb26/ora-ai-api/src/services/behavior-detection.service.ts
(Currently uses simple keyword matching with behavior.triggers.keywords and regex patterns)

BACKEND ROOT: /Users/matthew/Desktop/Feb26/ora-ai-api/
TECH STACK: Node.js + PostgreSQL + pgvector

THE 6 VECTOR TYPES TO DESIGN:
1. **User Message Vector** - Embedding of the user's current message
2. **Agent Message Vector** - Embedding of the AI agent's response
3. **Combined Agent+User Vector** - Joint embedding of conversation exchange
4. **Agent Inner Thought Vector** - Embedding of the agent's reasoning/intent
5. **External Events Vector** - Embedding of contextual events (time of day, user state, app events)
6. **Tool Call Vector** - Embedding of tool invocations and their results

BROADCAST SYSTEM DESIGN:
- When a message arrives, generate embeddings for applicable vector types
- Search each vector type against behavior trigger embeddings stored in pgvector
- Rank results by cosine similarity
- Feed top 20 candidates to LLM for final behavior selection
- Previously active behavior gets a persistence bonus

BEHAVIOR EXAMPLES (from existing config):
- Free-Form Chat (default fallback)
- Journal Prompting (guided journaling, 3-4 exchanges to completion)
- Guided Exercise (structured activities)
- Progress Analysis (review past sessions)
- Weekly Planning (set intentions)

DELIVERABLES:

1. **Architecture Document** at /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/multi-vector-system.md:
   - System overview diagram (ASCII or mermaid)
   - Data flow: message → embedding → search → rank → select
   - Each of the 6 vector types: purpose, when generated, dimensions, storage
   - Embedding model recommendation (OpenAI ada-002 or alternatives with trade-offs)
   - Vector dimensions and storage strategy
   - Similarity search approach (cosine similarity, HNSW index)
   - Broadcast algorithm pseudocode
   - LLM selection prompt template
   - Behavior persistence logic
   - Performance targets (<2s total latency)

2. **Database Schema** at /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/vector-schema.sql:
   - pgvector-enabled tables for each vector type
   - Behavior trigger embeddings table
   - Conversation state tracking table
   - HNSW indexes for fast similarity search
   - Migration script ready to execute

3. **API Design** at /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/vector-api.md:
   - Embedding generation endpoint design
   - Behavior detection endpoint design
   - Vector storage/retrieval endpoints
   - WebSocket events for real-time behavior updates
   - Rate limiting and caching strategy

4. **Implementation Plan** at /Users/matthew/Desktop/Feb26/ora-ai-api/docs/architecture/implementation-plan.md:
   - Task breakdown for downstream implementation
   - Dependencies between tasks
   - Recommended implementation order
   - Risk assessment and mitigation
   - Testing strategy for the vector system

STEPS:
1. Read the current behavior-detection.service.ts to understand existing patterns
2. Read the existing backend structure (services, routes, models, config)
3. Read the behaviors config to understand all behavior types
4. Design the vector system architecture
5. Write the database schema with pgvector support
6. Design the API endpoints
7. Write the implementation plan

REFERENCES:
- pgvector docs: https://github.com/pgvector/pgvector
- OpenAI embeddings API: text-embedding-ada-002 (1536 dimensions) or text-embedding-3-small (1536 dimensions)
- HNSW index: Good for approximate nearest neighbor search

ACCEPTANCE CRITERIA:
- All 6 vector types fully specified with purpose, generation logic, and storage
- Database schema is executable SQL with proper pgvector setup
- Architecture handles <2s end-to-end latency
- Broadcast system algorithm is clear and implementable
- LLM selection prompt template is included
- Implementation plan has clear task ordering

WHEN COMPLETE, run these commands:
```bash
curl -X PATCH http://localhost:3001/api/tasks/ORA-011 -H "Content-Type: application/json" -d '{"state": "done", "completed_at": "'$(date -u +%Y-%m-%dT%H:%M:%S.000Z)'"}'
curl -X POST http://localhost:3001/api/activity -H "Content-Type: application/json" -d '{"project_id": 3, "task_id": "ORA-011", "agent_type": "backend-dev", "action": "completed", "details": "Multi-vector architecture designed - 6 vector types, pgvector schema, broadcast system, implementation plan"}'
```

START NOW. This is the most critical task - take your time to get it right.
