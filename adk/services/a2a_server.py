"""
A2A Server - Agent-to-Agent Communication Server for ADK Framework.

This module provides a FastAPI router that implements the server-side of the
A2A (Agent-to-Agent) protocol. Any ADK workflow can be exposed as an A2A endpoint
by including this router in their FastAPI application.

Usage:
    from adk.services.a2a_server import create_a2a_router
    
    # Create router for your workflow
    a2a_router = create_a2a_router(
        workflow_path="path/to/workflow.yaml",
        app_name="my_agent",
        agent_id="my_unique_agent_id"
    )
    
    # Include in your FastAPI app
    app.include_router(a2a_router, prefix="/a2a")
"""

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Header
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# A2A Protocol Version
A2A_PROTOCOL_VERSION = "a2a/1.0"


class A2ARequest(BaseModel):
    """A2A Protocol Request Envelope."""
    protocol: str = Field(..., description="Protocol identifier (e.g., 'a2a/1.0')")
    id: str = Field(..., description="Unique message ID")
    source: str = Field(..., description="Source agent identifier")
    target: str = Field(..., description="Target agent identifier")
    payload: dict[str, Any] = Field(default_factory=dict, description="Request payload/state")


class A2AResponse(BaseModel):
    """A2A Protocol Response Envelope."""
    protocol: str = Field(default=A2A_PROTOCOL_VERSION, description="Protocol identifier")
    id: str = Field(..., description="Original message ID (echoed back)")
    status: str = Field(..., description="Response status: 'success' or 'error'")
    result: dict[str, Any] | str | None = Field(None, description="Result data on success")
    error: str | None = Field(None, description="Error message on failure")


def create_a2a_router(
    workflow_path: str | Path,
    app_name: str,
    agent_id: str,
    description: str = "A2A-enabled agent"
) -> APIRouter:
    """
    Create a FastAPI router for A2A communication.
    
    Args:
        workflow_path: Path to the workflow YAML file
        app_name: Application name for the orchestrator
        agent_id: Unique identifier for this agent (used to validate target)
        description: Human-readable description for API docs
        
    Returns:
        FastAPI APIRouter with A2A endpoints
    """
    router = APIRouter(tags=["A2A"])
    workflow_path = Path(workflow_path)
    
    @router.post(
        "",
        response_model=A2AResponse,
        summary="A2A Invoke",
        description=f"Invoke this agent via A2A protocol. Agent ID: {agent_id}"
    )
    async def a2a_invoke(
        request: A2ARequest,
        x_agent_protocol: str | None = Header(None, alias="X-Agent-Protocol")
    ) -> A2AResponse:
        """
        Handle incoming A2A requests.
        
        Validates the protocol, extracts payload, runs the workflow,
        and returns a standardized A2A response.
        """
        # Validate protocol version
        if request.protocol != A2A_PROTOCOL_VERSION:
            return A2AResponse(
                id=request.id,
                status="error",
                error=f"Unsupported protocol: {request.protocol}. Expected: {A2A_PROTOCOL_VERSION}"
            )
        
        # Validate target matches this agent
        if request.target != agent_id:
            return A2AResponse(
                id=request.id,
                status="error",
                error=f"Target mismatch. This agent is '{agent_id}', but request targets '{request.target}'"
            )
        
        logger.info(f"A2A request from '{request.source}' to '{agent_id}' (id: {request.id})")
        
        try:
            # Import here to avoid circular imports
            from adk.orchestrator import WorkflowOrchestrator
            
            # Initialize orchestrator
            orchestrator = WorkflowOrchestrator(app_name=app_name)
            orchestrator.load_workflow(str(workflow_path))
            
            # Generate session ID from A2A message ID
            session_id = f"a2a_{request.id}"
            
            # Extract initial state from payload
            initial_state = dict(request.payload)
            
            # Add A2A metadata to state
            initial_state["_a2a"] = {
                "source": request.source,
                "target": request.target,
                "message_id": request.id
            }
            
            # Build user input from payload
            user_input = json.dumps(request.payload)
            
            # Run the workflow
            result = await orchestrator.run_async(
                user_input=user_input,
                session_id=session_id,
                initial_state=initial_state,
            )
            
            # Get final state
            final_state = {}
            if orchestrator._session_service:
                try:
                    session = await orchestrator._session_service.get_session(
                        app_name=app_name,
                        user_id="default_user",
                        session_id=session_id
                    )
                    if session:
                        final_state = dict(session.state)
                        # Remove internal keys
                        final_state.pop("_a2a", None)
                except Exception as e:
                    logger.warning(f"Could not retrieve final session state: {e}")
            
            return A2AResponse(
                id=request.id,
                status="success",
                result={
                    "output": result,
                    "state": final_state
                }
            )
            
        except Exception as e:
            logger.error(f"A2A request failed: {e}", exc_info=True)
            return A2AResponse(
                id=request.id,
                status="error",
                error=str(e)
            )
    
    @router.post(
        "/stream",
        summary="A2A Invoke (Streaming)",
        description=f"Invoke this agent via A2A protocol with streaming response. Agent ID: {agent_id}"
    )
    async def a2a_invoke_stream(
        request: A2ARequest,
        x_agent_protocol: str | None = Header(None, alias="X-Agent-Protocol")
    ):
        """
        Handle incoming A2A requests with streaming response.
        """
        # Validate protocol version
        if request.protocol != A2A_PROTOCOL_VERSION:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported protocol: {request.protocol}. Expected: {A2A_PROTOCOL_VERSION}"
            )
        
        # Validate target
        if request.target != agent_id:
            raise HTTPException(
                status_code=400,
                detail=f"Target mismatch. This agent is '{agent_id}', but request targets '{request.target}'"
            )
        
        logger.info(f"A2A stream request from '{request.source}' to '{agent_id}' (id: {request.id})")
        
        async def event_generator():
            try:
                from adk.orchestrator import WorkflowOrchestrator
                
                orchestrator = WorkflowOrchestrator(app_name=app_name)
                orchestrator.load_workflow(str(workflow_path))
                
                session_id = f"a2a_{request.id}"
                initial_state = dict(request.payload)
                initial_state["_a2a"] = {
                    "source": request.source,
                    "target": request.target,
                    "message_id": request.id
                }
                
                user_input = json.dumps(request.payload)
                
                async for event in orchestrator.run_stream(
                    user_input=user_input,
                    session_id=session_id,
                    initial_state=initial_state,
                ):
                    if hasattr(event, "content") and event.content and hasattr(event.content, "parts"):
                        for part in event.content.parts or []:
                            text = getattr(part, "text", None)
                            if text:
                                yield f"data: {json.dumps({'protocol': A2A_PROTOCOL_VERSION, 'id': request.id, 'text': text})}\n\n"
                
                # Final event
                yield f"data: {json.dumps({'protocol': A2A_PROTOCOL_VERSION, 'id': request.id, 'status': 'success', 'event': 'done'})}\n\n"
                
            except Exception as e:
                logger.error(f"A2A stream failed: {e}", exc_info=True)
                yield f"data: {json.dumps({'protocol': A2A_PROTOCOL_VERSION, 'id': request.id, 'status': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(event_generator(), media_type="text/event-stream")
    
    @router.get(
        "/info",
        summary="Agent Info",
        description="Get information about this A2A agent"
    )
    async def a2a_info():
        """Return agent metadata for discovery."""
        return {
            "protocol": A2A_PROTOCOL_VERSION,
            "agent_id": agent_id,
            "description": description,
            "capabilities": ["invoke", "stream"]
        }
    
    return router
