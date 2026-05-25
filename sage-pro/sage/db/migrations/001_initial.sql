-- SAGE-PRO v2 Initial Migration
-- Creates all tables for the SAGE-PRO system

CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS vector;

-- §4.2 Users
CREATE TABLE IF NOT EXISTS users (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    google_id  VARCHAR(128) UNIQUE NOT NULL,
    email      VARCHAR(255) UNIQUE NOT NULL,
    name       VARCHAR(255),
    avatar_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen  TIMESTAMPTZ DEFAULT NOW()
);

-- §5.1 Conversations
CREATE TABLE IF NOT EXISTS conversations (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(255),
    started_at TIMESTAMPTZ DEFAULT NOW(),
    ended_at   TIMESTAMPTZ
);

-- §5.1 Messages
CREATE TABLE IF NOT EXISTS messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL,
    content         TEXT NOT NULL,
    embedding       VECTOR(1536),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS messages_emb_idx ON messages
    USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- §5.1 Corrections
CREATE TABLE IF NOT EXISTS corrections (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id           UUID REFERENCES users(id),
    conversation_id   UUID REFERENCES conversations(id),
    message_id        UUID REFERENCES messages(id),
    original_response TEXT NOT NULL,
    corrected_content TEXT,
    responsible_agents VARCHAR(64)[],
    penalty_applied    FLOAT[],
    detected_at        TIMESTAMPTZ DEFAULT NOW(),
    batch_processed    BOOLEAN DEFAULT FALSE
);

-- §7.3 Agent Weights
CREATE TABLE IF NOT EXISTS agent_weights (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    agent_name        VARCHAR(64) UNIQUE NOT NULL,
    weight            FLOAT NOT NULL DEFAULT 1.0,
    epsilon           FLOAT NOT NULL DEFAULT 0.15,
    total_corrections INTEGER DEFAULT 0,
    total_hard        INTEGER DEFAULT 0,
    total_soft        INTEGER DEFAULT 0,
    last_updated      TIMESTAMPTZ DEFAULT NOW()
);

INSERT INTO agent_weights (agent_name) VALUES
    ('architect'), ('implementer'), ('synthesizer'), ('red_team')
ON CONFLICT (agent_name) DO NOTHING;

-- §9.2 Daily Update Log
CREATE TABLE IF NOT EXISTS daily_update_log (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_date           DATE NOT NULL,
    corrections_count  INTEGER,
    agents_penalised   JSONB,
    centroid_mutations INTEGER,
    new_clusters       INTEGER,
    pruned_clusters    INTEGER,
    q_table_delta_norm FLOAT,
    duration_seconds   FLOAT,
    created_at         TIMESTAMPTZ DEFAULT NOW()
);
