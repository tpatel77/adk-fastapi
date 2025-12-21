"""ExternalAgent for invoking remote/network agents via HTTP."""

import logging
import re
from typing import Any, AsyncGenerator

import httpx
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

class ExternalAgent(BaseAgent):
    """
    A workflow agent that invokes an external service via HTTP.
    
    It sends the current session state (or specific inputs) to a URL
    and validates/stores the response.
    
    Example configuration:
        url: "https://api.example.com/summarize"
        method: "POST"
        headers: 
            Authorization: "Bearer {API_KEY}"
        output_key: "summary"
    """
    
    url: str = Field(..., description="Target URL")
    method: str = Field("POST", description="HTTP method")
    headers: dict[str, str] = Field(default_factory=dict, description="HTTP headers")
    output_key: str | None = Field(None, description="State key to store output")
    
    model_config = {"arbitrary_types_allowed": True}
    
    def _resolve_string(self, text: str, state: dict[str, Any]) -> str:
        """Resolve {placeholders} in a string using state."""
        if not text:
            return ""
            
        def replace_placeholder(match: re.Match[str]) -> str:
            state_key = match.group(1)
            # Check state first, then env vars? 
            # For now, just state. (State should contain env vars if loaded via tools)
            # BaseAgent doesn't inherently have access to os.environ unless put in state
            state_value = state.get(state_key, match.group(0))
            return str(state_value) if state_value is not None else ""
        
        return re.sub(r'\{(\w+)\}', replace_placeholder, text)

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        """Execute the external HTTP request."""
        
        state = dict(ctx.session.state) if ctx.session else {}
        
        # Resolve URL and Headers
        resolved_url = self._resolve_string(self.url, state)
        resolved_headers = {
            k: self._resolve_string(v, state) 
            for k, v in self.headers.items()
        }
        
        # Prepare payload
        # By default, send the whole state? Or just specific inputs?
        # A generic agent usually sends context.
        # Sending whole state might be too much.
        # ADK doesn't specify which inputs "arrive".
        # Let's send the state as JSON body for POST/PUT.
        # For GET, maybe query params?
        
        json_body = None
        params = None
        
        if self.method.upper() in ["POST", "PUT", "PATCH"]:
            json_body = state
        else:
            params = state  # Try to put state in query params for GET? might be large.
        
        logger.info(f"ExternalAgent '{self.name}' calling {self.method} {resolved_url}")
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.request(
                    method=self.method,
                    url=resolved_url,
                    headers=resolved_headers,
                    json=json_body,
                    params=params,
                    timeout=30.0
                )
                
                response.raise_for_status()
                
                # Try parsing JSON
                try:
                    result_data = response.json()
                    # If result is strict JSON, store it?
                    # If user wants a specific field, we can't easily extracting it without more config.
                    # Let's store the whole JSON or text.
                    result_str = str(result_data)
                except Exception:
                    # Fallback to text
                    result_str = response.text
                
        except Exception as e:
            error_msg = f"External request failed: {str(e)}"
            logger.error(error_msg)
            result_str = f"Error: {error_msg}"
            
            # Should we raise or yield error?
            # Creating an event with error info is usually better for workflow cont.
        
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
