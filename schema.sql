-- ADK Session Service Schema for PostgreSQL
-- These tables are auto-created by DatabaseSessionService, but can be pre-created manually.

-- =============================================================================
-- APP STATES: Global state shared across ALL sessions for an application
-- =============================================================================
CREATE TABLE IF NOT EXISTS app_states (
    app_name             VARCHAR(255) NOT NULL PRIMARY KEY,
    state                JSONB NOT NULL DEFAULT '{}'::jsonb,
    update_time          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- =============================================================================
-- USER STATES: State shared across sessions for a specific user
-- =============================================================================
CREATE TABLE IF NOT EXISTS user_states (
    app_name             VARCHAR(255) NOT NULL,
    user_id              VARCHAR(255) NOT NULL,
    state                JSONB NOT NULL DEFAULT '{}'::jsonb,
    update_time          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (app_name, user_id)
);

-- =============================================================================
-- SESSIONS: Per-session state and metadata
-- =============================================================================
CREATE TABLE IF NOT EXISTS sessions (
    app_name             VARCHAR(255) NOT NULL,
    user_id              VARCHAR(255) NOT NULL,
    id                   VARCHAR(255) NOT NULL,
    state                JSONB NOT NULL DEFAULT '{}'::jsonb,
    create_time          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    update_time          TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (app_name, user_id, id)
);

-- Index for fast user-app lookups
CREATE INDEX IF NOT EXISTS idx_sessions_user_app ON sessions(user_id, app_name);

-- =============================================================================
-- EVENTS: Complete event history for each session
-- =============================================================================
CREATE TABLE IF NOT EXISTS events (
    id                   VARCHAR(255) NOT NULL,
    app_name             VARCHAR(255) NOT NULL,
    user_id              VARCHAR(255) NOT NULL,
    session_id           VARCHAR(255) NOT NULL,
    invocation_id        VARCHAR(255) NOT NULL,
    author               VARCHAR(255) NOT NULL,
    actions              BYTEA NOT NULL,
    timestamp            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Content and metadata (nullable)
    content              JSONB,
    branch               VARCHAR(255),
    partial              BOOLEAN,
    turn_complete        BOOLEAN,
    interrupted          BOOLEAN,
    
    -- Error handling
    error_code           VARCHAR(255),
    error_message        VARCHAR(1024),
    
    -- Tool execution
    long_running_tool_ids_json TEXT,
    
    -- Metadata objects
    grounding_metadata   JSONB,
    custom_metadata      JSONB,
    usage_metadata       JSONB,
    citation_metadata    JSONB,
    
    -- Transcription (for audio/voice)
    input_transcription  JSONB,
    output_transcription JSONB
    ,
    PRIMARY KEY (id, app_name, user_id, session_id),
    FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES sessions(app_name, user_id, id)
        ON DELETE CASCADE
);

-- Index for fast session event retrieval
CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id);
CREATE INDEX IF NOT EXISTS idx_events_invocation ON events(invocation_id);

-- =============================================================================
-- RAG SYSTEM EXTENSIONS
-- =============================================================================

-- 1. PROJECTS
CREATE TABLE IF NOT EXISTS projects (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 VARCHAR(255) NOT NULL UNIQUE,
    description          TEXT,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 2. STRATEGIES (Catalog of available strategies)
-- Types: 'knowledge_base', 'query_processing'
CREATE TABLE IF NOT EXISTS strategies (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name                 VARCHAR(255) NOT NULL UNIQUE,
    type                 VARCHAR(50) NOT NULL CHECK (type IN ('knowledge_base', 'query_processing')),
    description          TEXT,
    default_config       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 3. PIPELINE CONFIGURATIONS (Active strategies per project)
CREATE TABLE IF NOT EXISTS pipeline_configs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    strategy_id          UUID NOT NULL REFERENCES strategies(id),
    config               JSONB NOT NULL DEFAULT '{}'::jsonb, -- Custom overrides
    is_active            BOOLEAN DEFAULT TRUE,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 4. ACTIVITY LOGS (Who ran what)
CREATE TABLE IF NOT EXISTS activity_logs (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           VARCHAR(255) NOT NULL, -- References sessions(id) logically
    project_id           UUID REFERENCES projects(id),
    user_id              VARCHAR(255) NOT NULL,
    workflow_config      JSONB, -- Snapshot of config used
    timestamp            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- 5. TOKEN USAGE (Granular tracking)
CREATE TABLE IF NOT EXISTS token_usage (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id           VARCHAR(255) NOT NULL,
    agent_name           VARCHAR(255) NOT NULL,
    model_name           VARCHAR(255),
    input_tokens         INTEGER DEFAULT 0,
    output_tokens        INTEGER DEFAULT 0,
    total_tokens         INTEGER DEFAULT 0,
    timestamp            TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed some default strategies
INSERT INTO strategies (name, type, description) VALUES 
('hybrid_rag', 'knowledge_base', 'Combines sparse and dense retrieval indexing'),
('context_retrieval', 'knowledge_base', 'Enriches chunks with surrounding context'),
('retrieval_verification', 'query_processing', 'Verifies retrieved documents against query'),
('self_rag', 'query_processing', 'Agent reflects on its own retrieval and generation')
ON CONFLICT (name) DO NOTHING;


-- =============================================================================
-- VECTOR DB METADATA (2.6 & 2.7)
-- =============================================================================

CREATE TABLE IF NOT EXISTS vector_db_config (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id           UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    workflow_name        VARCHAR(255) NOT NULL, -- Logical name of the workflow
    collection_name      VARCHAR(255) NOT NULL,
    metadata_fields      JSONB NOT NULL DEFAULT '[]'::jsonb, -- List of field names/descriptions
    description          TEXT,
    created_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at           TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Ensure unique collection mapping per workflow
    UNIQUE(project_id, workflow_name, collection_name)
);
