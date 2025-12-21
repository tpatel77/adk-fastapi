"""A2AAgent for standardized Agent-to-Agent communication."""

import logging
import uuid
import uuid as uuid_lib  # Alias for explicit usage
from typing import AsyncGenerator

import httpx
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

class A2AAgent(BaseAgent):
    """
    A workflow agent that speaks the Standard A2A Protocol (v1).
    
    It wraps the session state in a standardized envelope and expects
    a standardized response.
    
    Protocol Spec:
        Request:
        {
          "protocol": "a2a/1.0",
          "id": "uuid",
          "source": "agent_name",
          "target": "target_agent_id",
          "payload": { ... state ... }
        }
        
        Response:
        {
          "protocol": "a2a/1.0",
          "status": "success"|"error",
          "result": { ... output ... }
        }
    """
    
    url: str = Field(..., description="Target Endpoint URL")
    target_agent_id: str = Field(..., description="ID of the destination agent")
    output_key: str | None = Field(None, description="State key to store output")
    
    model_config = {"arbitrary_types_allowed": True}

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        """Execute the A2A request."""
        state = dict(ctx.session.state) if ctx.session else {}
        
        # Construct A2A Envelope
        interaction_id = str(uuid_lib.uuid4())
        
        envelope = {
            "protocol": "a2a/1.0",
            "id": interaction_id,
            "source": self.name,
            "target": self.target_agent_id,
            "payload": state
        }
        
        logger.info(f"A2AAgent '{self.name}' sending message to '{self.target_agent_id}' at {self.url}")
        
        result_str = ""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.url,
                    json=envelope,
                    headers={
                        "Content-Type": "application/json",
                        "X-Agent-Protocol": "a2a/1.0"
                    },
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                # Parse Response Envelope
                try:
                    resp_data = response.json()
                    
                    # Validate Protocol
                    if resp_data.get("protocol") != "a2a/1.0":
                        logger.warning(f"Response protocol mismatch: {resp_data.get('protocol')}")
                        
                    if resp_data.get("status") == "error":
                        raise RuntimeError(f"A2A Error: {resp_data.get('error', 'Unknown error')}")
                        
                    # Extract Result
                    result = resp_data.get("result", {})
                    result_str = str(result)
                    
                    # Optional: Unwrap specific output key if configured?
                    # For now, store the whole result object string representation
                    
                except Exception as e:
                    logger.error(f"Failed to parse A2A response: {e}")
                    result_str = f"Error parsing response: {response.text}"
                    
        except Exception as e:
            error_msg = f"A2A request failed: {str(e)}"
            logger.error(error_msg)
            result_str = f"Error: {error_msg}"
        
        # Store result
        if self.output_key and ctx.session:
            ctx.session.state[self.output_key] = result_str
            
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=result_str)],
            ),
        )
