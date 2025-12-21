
# from fastapi import APIRouter, HTTPException, Depends
# from pydantic import BaseModel, Field
# from typing import List, Optional, Any, Dict
# from uuid import UUID
# import datetime
# import json

# from .database import db

# router = APIRouter(tags=["Onboarding & Customization"])

# # --- Models ---

# class ProjectCreate(BaseModel):
#     name: str
#     description: Optional[str] = None

# class StrategyCreate(BaseModel):
#     name: str
#     type: str = Field(..., pattern="^(knowledge_base|query_processing)$")
#     description: Optional[str] = None
#     default_config: Dict[str, Any] = {}

# class PipelineConfigUpdate(BaseModel):
#     strategy_name: str
#     config: Dict[str, Any] = {}
#     is_active: bool = True

# class ActivityLogCreate(BaseModel):
#     project_id: Optional[UUID] = None
#     session_id: str
#     user_id: str
#     workflow_config: Dict[str, Any]

# class TokenUsageCreate(BaseModel):
#     session_id: str
#     agent_name: str
#     model_name: Optional[str] = None
#     input_tokens: int = 0
#     output_tokens: int = 0

# # --- 1. Project Management ---

# @router.post("/projects/", response_model=Dict[str, Any])
# async def create_project(project: ProjectCreate):
#     """Create a new RAG project."""
#     query = """
#         INSERT INTO projects (name, description) 
#         VALUES ($1, $2) 
#         RETURNING id, name, created_at
#     """
#     try:
#         res = await db.fetch_one(query, project.name, project.description)
#         return res
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# @router.get("/projects/", response_model=List[Dict[str, Any]])
# async def list_projects():
#     return await db.fetch_all("SELECT * FROM projects")

# # --- 2. Strategy Management ---

# @router.post("/strategies/", response_model=Dict[str, Any])
# async def create_strategy(strategy: StrategyCreate):
#     """Add a new available strategy (2.1.2 & 2.2.2)."""
#     query = """
#         INSERT INTO strategies (name, type, description, default_config)
#         VALUES ($1, $2, $3, $4)
#         RETURNING id, name
#     """
#     try:
#         res = await db.fetch_one(query, strategy.name, strategy.type, strategy.description, strategy.default_config)
#         return res
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# @router.get("/strategies/", response_model=List[Dict[str, Any]])
# async def list_strategies(type: Optional[str] = None):
#     if type:
#         return await db.fetch_all("SELECT * FROM strategies WHERE type = $1", type)
#     return await db.fetch_all("SELECT * FROM strategies")

# # --- 3. Pipeline Configuration (2.1.1 & 2.2.1) ---

# @router.post("/projects/{project_id}/pipeline", response_model=Dict[str, Any])
# async def configure_pipeline(project_id: UUID, config: PipelineConfigUpdate):
#     """
#     Configure a pipeline strategy for a project.
#     Can be used for both Document Processing (KB) and Query Processing.
#     """
#     # 1. Get Strategy ID
#     strat = await db.fetch_one("SELECT id, type FROM strategies WHERE name = $1", config.strategy_name)
#     if not strat:
#         raise HTTPException(status_code=404, detail="Strategy not found")
    
#     # 2. Upsert Pipeline Config
#     # We assume one active config per strategy-project pair? Or just insert?
#     # Requirement: "select the strategies... configurations stored in database"
    
#     query = """
#         INSERT INTO pipeline_configs (project_id, strategy_id, config, is_active)
#         VALUES ($1, $2, $3, $4)
#         RETURNING id, created_at
#     """
#     # Note: A smarter implementation might handle updating existing config for the same strategy
    
#     try:
#         res = await db.fetch_one(
#             query, 
#             project_id, 
#             strat['id'], 
#             config.config, 
#             config.is_active
#         )
#         return {**res, "type": strat['type']}
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# # --- 4. Manual Workflow Update Helper (2.1.3 & 2.2.3) ---

# @router.get("/projects/{project_id}/workflow-config")
# async def get_project_workflow_config(project_id: UUID):
#     """
#     Returns the consolidated configuration of all active strategies for a project.
#     This aids the manual update of the workflow YAML.
#     """
#     query = """
#         SELECT s.name as strategy_name, s.type as pipeline_type, pc.config
#         FROM pipeline_configs pc
#         JOIN strategies s ON pc.strategy_id = s.id
#         WHERE pc.project_id = $1 AND pc.is_active = TRUE
#         ORDER BY pc.created_at DESC
#     """
#     configs = await db.fetch_all(query, project_id)
#     return {
#         "project_id": str(project_id),
#         "active_strategies": configs,
#         "instructions": "Use these strategies to manually update your document_processor.yaml or query_workflow.yaml"
#     }

# # --- 5. Activity Tracking (2.3) ---

# @router.post("/activity/log")
# async def track_activity(log: ActivityLogCreate):
#     """Track user activity and workflow config used."""
#     query = """
#         INSERT INTO activity_logs (project_id, session_id, user_id, workflow_config)
#         VALUES ($1, $2, $3, $4)
#         RETURNING id
#     """
#     try:
#         res = await db.fetch_one(query, log.project_id, log.session_id, log.user_id, log.workflow_config)
#         return res
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# # --- 6. Token Tracking (2.4) ---

# @router.post("/metrics/tokens")
# async def track_tokens(usage: TokenUsageCreate):
#     """Track token usage per agent/session."""
#     query = """
#         INSERT INTO token_usage (session_id, agent_name, model_name, input_tokens, output_tokens, total_tokens)
#         VALUES ($1, $2, $3, $4, $5, $6)
#         RETURNING id
#     """
#     total = usage.input_tokens + usage.output_tokens
#     try:
#         res = await db.fetch_one(
#             query, 
#             usage.session_id, 
#             usage.agent_name, 
#             usage.model_name, 
#             usage.input_tokens, 
#             usage.output_tokens, 
#             total
#         )
#         return res
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# # --- 7. Tool Integration (2.5) ---

# @router.get("/integration/agent-config")
# async def get_agent_integration_config(project_id: UUID, session_id: Optional[str] = None):
#     """
#     API for tools/agents to fetch current project settings.
#     Feeding workflow configurations to agents.
#     """
#     # Simply re-use the workflow config logic but maybe formatted for an agent
#     cfg = await get_project_workflow_config(project_id)
#     return {
#         "instruction": "Below is the active configuration for the RAG pipelines.",
#         "configuration": cfg
#     }


# # --- 8. Vector DB Configuration (2.6 & 2.7) ---

# class VectorDBConfigCreate(BaseModel):
#     project_id: UUID
#     workflow_name: str
#     collection_name: str
#     metadata_fields: List[str] = [] # e.g. ["source", "author", "date"]
#     description: Optional[str] = None

# @router.post("/vector-db/config", response_model=Dict[str, Any])
# async def save_vector_db_config(config: VectorDBConfigCreate):
#     """
#     Save the vector DB collection and metadata fields for a specific workflow.
#     (Requirement 2.6)
#     """
#     # Check if project exists
#     proj = await db.fetch_one("SELECT id FROM projects WHERE id = $1", config.project_id)
#     if not proj:
#         raise HTTPException(status_code=404, detail="Project not found")

#     query = """
#         INSERT INTO vector_db_config 
#         (project_id, workflow_name, collection_name, metadata_fields, description)
#         VALUES ($1, $2, $3, $4, $5)
#         ON CONFLICT (project_id, workflow_name, collection_name) 
#         DO UPDATE SET 
#             metadata_fields = EXCLUDED.metadata_fields,
#             description = EXCLUDED.description,
#             updated_at = CURRENT_TIMESTAMP
#         RETURNING id, collection_name, metadata_fields, updated_at
#     """
#     try:
#         res = await db.fetch_one(
#             query,
#             config.project_id,
#             config.workflow_name,
#             config.collection_name,
#             json.dumps(config.metadata_fields),
#             config.description
#         )
#         # Parse JSONB back to list for response
#         if res and 'metadata_fields' in res:
#              res['metadata_fields'] = json.loads(res['metadata_fields'])
#         return res
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))

# @router.get("/vector-db/config", response_model=List[Dict[str, Any]])
# async def get_vector_db_config(project_id: UUID, workflow_name: Optional[str] = None):
#     """
#     Get the vector DB collection and metadata fields.
#     (Requirement 2.7)
#     """
#     query = """
#         SELECT id, workflow_name, collection_name, metadata_fields, description, updated_at
#         FROM vector_db_config
#         WHERE project_id = $1
#     """
#     args = [project_id]
    
#     if workflow_name:
#         query += " AND workflow_name = $2"
#         args.append(workflow_name)
    
#     try:
#         records = await db.fetch_all(query, *args)
#         # Parse JSON fields
#         for r in records:
#             if 'metadata_fields' in r and isinstance(r['metadata_fields'], str):
#                  r['metadata_fields'] = json.loads(r['metadata_fields'])
#         return records
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=str(e))
