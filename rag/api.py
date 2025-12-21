"""
FastAPI server for RAG Document Processing.
Exposes an endpoint to process documents using the ADK workflow framework.
"""

import base64
import json
from typing import Any, Union
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from adk.orchestrator import WorkflowOrchestrator
from adk.llm_gateway.x42_gateway_adk import X42GatewayADK
from litellm import completion as litellm_completion
# from .onboarding_api import router as onboarding_router

# from .onboarding_api import router as onboarding_router, db

app = FastAPI(
    title="RAG Document Processor",
    description="API for processing documents using ADK workflows",
    version="1.0.0"
)

try:
    from fastapi_common.middleware.request_context_middleware import RequestContextMiddleware

    app.add_middleware(RequestContextMiddleware)
except Exception:
    pass

# Include the onboarding/onfiguration endpoints
# app.include_router(onboarding_router, prefix="/api/v1")

# @app.on_event("startup")
# async def startup():
#     await db.connect()
#     # Initialize Schema
#     try:
#         schema_path = Path(__file__).parent.parent / "schema.sql"
#         if schema_path.exists():
#             with open(schema_path, "r") as f:
#                 schema_sql = f.read()
#             # asyncpg execute can handle multiple statements if simple, but fetch/execute might splitting issues.
#             # Using execute for script
#             await db.execute(schema_sql)
#             print("Schema initialized.")
#     except Exception as e:
#         print(f"Warning: Schema initialization failed: {e}")

@app.on_event("shutdown")
async def shutdown():
    try:
        db = globals().get("db")
        if db is not None:
            await db.disconnect()
    except Exception:
        pass

# Path to the workflow YAML
WORKFLOW_PATH = Path(__file__).parent / "document_processor.yaml"


class DocumentRequest(BaseModel):
    """Request model for document processing."""
    document: Union[str, dict[str, Any]] = Field(
        ..., 
        description="Document content - can be a string or JSON object"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Document metadata as JSON"
    )
    state: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional initial session state to merge into workflow state"
    )
    session_id: str | None = Field(None, description="Session ID to resume execution (optional)")


class DocumentResponse(BaseModel):
    """Response model for document processing."""
    status: str
    session_id: str
    result: str
    state: dict[str, Any] = Field(default_factory=dict)


class LiteLLMUsageRequest(BaseModel):
    messages: list[dict[str, Any]] = Field(..., min_length=1)
    experience_id: str | None = None
    model: str = "custom"
    prompt_id: str


@app.post("/process", response_model=DocumentResponse)
async def process_document(request: DocumentRequest):
    """
    Process a document using the document_processor workflow.
    
    Args:
        request: DocumentRequest containing document and metadata
        
    Returns:
        DocumentResponse with processing results
    """
    try:
        # Convert document to string if it's a dict
        if isinstance(request.document, dict):
            document_str = json.dumps(request.document)
        else:
            document_str = request.document
            
        # Create user input combining document and metadata
        user_input = f"Document: {document_str}\nMetadata: {json.dumps(request.metadata)}"
        
        # Initialize orchestrator and load workflow
        orchestrator = WorkflowOrchestrator(app_name="rag_processor")
        orchestrator.load_workflow(str(WORKFLOW_PATH))
        
        # Generate unique session ID
        import uuid
        session_id = request.session_id or str(uuid.uuid4())
        
        # Run the workflow
        initial_state = {
            "document": document_str,
            "metadata": request.metadata,
        }
        if request.state:
            initial_state.update(request.state)
        result = await orchestrator.run_async(
            user_input=user_input,
            session_id=session_id,
            initial_state=initial_state,
        )
        
        # Get final state from session
        final_state = {}
        if orchestrator._session_service:
            try:
                session = await orchestrator._session_service.get_session(
                    app_name="rag_processor", 
                    user_id="default_user", 
                    session_id=session_id
                )
                if session:
                    final_state = session.state
            except Exception:
                # Some session services may not support get_session after run
                pass
        
        return DocumentResponse(
            status="success",
            session_id=session_id,
            result=result,
            state=final_state
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/stream")
async def process_document_stream(request: DocumentRequest):
    try:
        if isinstance(request.document, dict):
            document_str = json.dumps(request.document)
        else:
            document_str = request.document

        user_input = f"Document: {document_str}\nMetadata: {json.dumps(request.metadata)}"

        orchestrator = WorkflowOrchestrator(app_name="rag_processor")
        orchestrator.load_workflow(str(WORKFLOW_PATH))

        import uuid
        session_id = str(uuid.uuid4())

        async def event_generator():
            initial_state = {
                "document": document_str,
                "metadata": request.metadata,
            }
            if request.state:
                initial_state.update(request.state)
            async for event in orchestrator.run_stream(
                user_input=user_input,
                session_id=session_id,
                initial_state=initial_state,
            ):
                if hasattr(event, "content") and event.content and hasattr(event.content, "parts"):
                    for part in event.content.parts or []:
                        text = getattr(part, "text", None)
                        if text:
                            yield f"data: {json.dumps({'text': text})}\n\n"

                        function_call = getattr(part, "function_call", None)
                        if function_call is not None:
                            name = getattr(function_call, "name", None)
                            args = getattr(function_call, "args", None)
                            if name:
                                yield f"data: {json.dumps({'tool_call': {'name': name, 'args': args}})}\n\n"

            yield f"data: {json.dumps({'event': 'done', 'session_id': session_id})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/debug/litellm-usage")
async def debug_litellm_usage(request: LiteLLMUsageRequest):
    try:
        gateway = X42GatewayADK()
        headers = gateway._build_headers({"experience_id": request.experience_id})

        model_name = request.model
        if not model_name.startswith("openai/"):
            model_name = f"openai/{model_name}"

        system_prompt = {"promptId": request.prompt_id, "variables": {}}
        system_message = {
            "role": "system",
            "content": base64.b64encode(json.dumps(system_prompt).encode()).decode(),
        }

        resp = litellm_completion(
            model=model_name,
            api_base=gateway.url,
            api_key="not-required",
            messages=[system_message] + request.messages,
            stream=False,
            extra_headers=headers,
        )

        if hasattr(resp, "model_dump"):
            return resp.model_dump()
        if isinstance(resp, dict):
            return resp
        if hasattr(resp, "json"):
            return json.loads(resp.json())
        return {"raw": str(resp)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
