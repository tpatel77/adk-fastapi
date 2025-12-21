"""RouterAgent for conditional workflow routing."""

import logging
import re
from typing import Any, AsyncGenerator, Callable

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

class RouterAgent(BaseAgent):
    """
    A workflow agent that routes execution to one of its sub-agents based on a condition.
    
    The condition is a Python expression evaluated against the session state.
    
    Example configuration:
        condition: "{sentiment_score} < 0.5"
        routes:
          "True": handle_negative_agent
          "False": handle_positive_agent
    """
    
    condition: str = Field(..., description="Python expression to evaluate")
    routes: dict[str, BaseAgent] = Field(..., description="Map of condition results to sub-agents")
    
    model_config = {"arbitrary_types_allowed": True}
    
    def _evaluate_condition(self, state: dict[str, Any]) -> str:
        """
        Evaluate the python condition against state.
        Returns the result as a string key to look up in routes.
        """
        # 1. Substitute state variables: "{var}" -> value
        # We need to be careful about types. 
        # A safer way is to use eval() with state as locals.
        
        try:
            # Prepare state for eval
            # We strip {} from the condition string placeholders if users used them
            # But standard python eval doesn't need {} for variables if they are in locals.
            # However, our config format might encourage "{var}". 
            # Let's support standard python expressions with variables from state.
            
            # If user wrote "{sentiment} > 0.5", we want to evaluate "sentiment > 0.5" 
            # with sentiment in the context.
            # So first, let's substitute {key} with the actual value or just rely on variable names matching.
            
            # Simple approach: Replace {key} with values, then eval. 
            # But values might be strings needing quotes.
            
            # Better approach: Pass state as the context to eval. 
            # User should write "sentiment > 0.5" not "{sentiment} > 0.5" for python eval,
            # BUT to be consistent with our other tools, users might expect {}.
            
            # let's try to support both or format the string first.
            formatted_condition = self.condition
            
            # Simple formatting for direct substitution (classic f-string style)
            # This is risky for code evaluation if not careful, but this is a local tool.
            # Let's use string.format taking state as kwargs?
            # No, that generates a string. We want to evaluate logic.
            
            # Let's remove {} if present to allow variable access
            clean_condition = re.sub(r'\{(\w+)\}', r'\1', self.condition)
            
            result = eval(clean_condition, {}, state)
            return str(result)
            
        except Exception as e:
            logger.error(f"Error evaluating condition '{self.condition}': {e}")
            # Fallback or re-raise? Let's return error as detailed string key? 
            # No, let's treat error as "False" or raise.
            # Raising is safer to debug configuration errors.
            raise ValueError(f"Router condition evaluation failed: {e}")

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        """Execute the router logic."""
        
        state = dict(ctx.session.state) if ctx.session else {}
        
        # Evaluate condition
        result_key = self._evaluate_condition(state)
        
        logger.info(f"Router '{self.name}' condition '{self.condition}' evaluated to: {result_key}")
        
        # Select agent
        selected_agent = self.routes.get(result_key)
        
        if not selected_agent:
            # Try boolean normalization (True/False vs "True"/"False")
            if result_key == "True":
                selected_agent = self.routes.get("true") or self.routes.get(True)
            elif result_key == "False":
                selected_agent = self.routes.get("false") or self.routes.get(False)
        
        if not selected_agent:
            # Yield an error event or just stop?
            # If no route matches, we essentially "dropped" the packet.
            # Better to inform.
            error_msg = f"Router '{self.name}': No route found for result '{result_key}' (Routes: {list(self.routes.keys())})"
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=error_msg)],
                ),
            )
            return

        # Run the selected sub-agent
        # We call _run_async_impl directly, passing the InvocationContext
        # This is how ADK internally delegates execution to sub-agents
        async for event in selected_agent._run_async_impl(ctx):
            yield event
