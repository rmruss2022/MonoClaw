# ORA-075: Set up pgvector extension for vector storage

**Priority:** Critical (P0)
**Type:** Backend Development
**Estimated:** 4 hours
**Dependencies:** None
**Tags:** backend, database, infrastructure, AI

## 🎯 Objective

Set up PostgreSQL pgvector extension to enable vector similarity search for AI-powered features (semantic search, content recommendations, trigger matching).

## 📋 Requirements

### 1. Install pgvector Extension
- Install pgvector in the Ora AI PostgreSQL database
- Verify installation with `SELECT * FROM pg_available_extensions WHERE name = 'pgvector';`
- Create extension: `CREATE EXTENSION IF NOT EXISTS vector;`

### 2. Create Embeddings Table
```sql
CREATE TABLE embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    content_hash TEXT UNIQUE NOT NULL,
    vector vector(1536) NOT NULL,  -- OpenAI ada-002 dimension
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

**Fields:**
- `content_hash`: SHA-256 hash of original text (for deduplication)
- `vector`: 1536-dimension vector (OpenAI text-embedding-ada-002)
- `metadata`: Store source info (type, user_id, context)

### 3. Create behavior_triggers_embeddings Table
```sql
CREATE TABLE behavior_triggers_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    trigger_text TEXT NOT NULL,
    behavior_id UUID NOT NULL REFERENCES behaviors(id),
    vector vector(1536) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (behavior_id) REFERENCES behaviors(id) ON DELETE CASCADE
);
```

### 4. Add HNSW Index for Fast Similarity Search
```sql
-- HNSW index for cosine similarity (best for normalized embeddings)
CREATE INDEX ON embeddings USING hnsw (vector vector_cosine_ops);

-- HNSW index for behavior triggers
CREATE INDEX ON behavior_triggers_embeddings USING hnsw (vector vector_cosine_ops);
```

**HNSW Parameters:**
- Default is fine for <100k vectors
- Tune `m` and `ef_construction` if performance issues arise

### 5. Create Helper Functions
```sql
-- Function to find similar embeddings
CREATE OR REPLACE FUNCTION find_similar_embeddings(
    query_vector vector(1536),
    match_threshold float DEFAULT 0.7,
    match_count int DEFAULT 5
)
RETURNS TABLE (
    id UUID,
    content_hash TEXT,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        e.id,
        e.content_hash,
        1 - (e.vector <=> query_vector) AS similarity
    FROM embeddings e
    WHERE 1 - (e.vector <=> query_vector) > match_threshold
    ORDER BY e.vector <=> query_vector
    LIMIT match_count;
END;
$$ LANGUAGE plpgsql;
```

### 6. Migration Script
Create migration file: `migrations/YYYY-MM-DD-pgvector-setup.sql`

Include:
- Extension installation
- Table creation
- Index creation
- Helper functions
- Rollback statements (DROP commands)

## 🔍 Testing Criteria

### Unit Tests
1. **Extension installed:** Query `pg_available_extensions`
2. **Tables exist:** Check `embeddings` and `behavior_triggers_embeddings` tables
3. **Indexes created:** Verify HNSW indexes exist
4. **Insert test vector:** 
   ```sql
   INSERT INTO embeddings (content_hash, vector) 
   VALUES ('test_hash', array_fill(0.1, ARRAY[1536])::vector);
   ```
5. **Similarity search:** Test `find_similar_embeddings()` function
6. **Performance:** Query with EXPLAIN ANALYZE, verify index usage

### Performance Targets
- **Similarity search:** <50ms for 10k vectors, <200ms for 100k vectors
- **Index creation:** <30 seconds for empty tables
- **Batch inserts:** >1000 vectors/second

## 📁 File Structure
```
ora-ai-api/
├── migrations/
│   └── 2026-02-13-pgvector-setup.sql
├── src/db/
│   └── vector-setup.ts (programmatic setup if needed)
└── tests/
    └── vector-db.test.ts
```

## ✅ Acceptance Criteria

- [ ] pgvector extension installed and enabled
- [ ] `embeddings` table created with vector(1536) column
- [ ] `behavior_triggers_embeddings` table created
- [ ] HNSW indexes created on both tables
- [ ] Helper function `find_similar_embeddings()` works correctly
- [ ] Migration script is idempotent (can run multiple times safely)
- [ ] Test vectors can be inserted and queried
- [ ] Similarity search returns results in <200ms
- [ ] Documentation added to README explaining vector setup

## 🚀 Next Steps After Completion

This unblocks:
- ORA-012: Implement embedding generation service
- ORA-013: Create behavior trigger matching system
- ORA-014: Implement semantic search for letters
- All AI-powered recommendation features

## 📚 Resources

- [pgvector GitHub](https://github.com/pgvector/pgvector)
- [OpenAI Embeddings](https://platform.openai.com/docs/guides/embeddings)
- [HNSW Index Tuning](https://github.com/pgvector/pgvector#hnsw)

## 🎯 Agent Type Required

**Backend-Dev Agent** with:
- PostgreSQL expertise
- Migration script experience
- Vector database knowledge (nice to have)
- SQL optimization skills
