from typing import Any, AsyncGenerator, Optional
import logging
import base64
import json

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

class WorkflowInterruption(Exception):
    """Exception raised to signal a workflow interruption (pause)."""
    def __init__(self, agent_name: str, message: str, mode: str, resume_key: str):
        self.agent_name = agent_name
        self.message = message
        self.mode = mode
        self.resume_key = resume_key
        super().__init__(f"Interrupt by {agent_name}: {message}")

class InterruptAgent(BaseAgent):
    """
    Agent that pauses execution to wait for external input.
    """
    interaction_mode: str = Field("text_input", description="Mode: 'text_input', 'approval', etc.")
    message: str | None = Field(None, description="Prompt message for the user")
    
    # LLM Capability
    llm_agent: BaseAgent | None = Field(None, description="LLM Agent to generate the prompt message")

    model_config = {"arbitrary_types_allowed": True}
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not ctx.session:
            return
            
        state = ctx.session.state
        
        # 1. Check if we have an answer (Resume)
        if self.output_key in state:
            answer = state[self.output_key]
            logger.info(f"InterruptAgent '{self.name}' resuming with answer: {answer}")
            yield Event(
                author=self.name,
                content=types.Content(
                    role="model",
                    parts=[types.Part(text=f"Resumed with: {answer}")],
                )
            )
            return

        # 2. Prepare Message
        interrupt_msg = self.message or ""
        
        # Option A: Run LLM Agent to generate the question
        if self.llm_agent:
            # We run the attached LLM agent. Its output (which usually goes to state via output_key)
            # is what we want to be the 'message'.
            # But the LLM Agent stores to state. We need to capture it.
            # ADK Agents yield events.
            
            logger.info(f"InterruptAgent '{self.name}' generating prompt via LLM...")
            
            generated_text = ""
            async for event in self.llm_agent._run_async_impl(ctx):
                # yield event # Should we yield the generation steps? Maybe not, to avoid confusion.
                # Just capture the final text.
                if event.content and event.content.parts:
                    for p in event.content.parts:
                        if p.text:
                            generated_text = p.text
            
            if generated_text:
                interrupt_msg = generated_text
        
        # Option B: Run Tool (Dynamic Context)
        if self.tool_func:
             try:
                 # Resolve args
                 from adk.core.tool_agent import ToolAgent
                 resolved_args = self.tool_args.copy() 
                 # TODO: Substitutions
                 
                 import inspect
                 if inspect.iscoroutinefunction(self.tool_func):
                     res = await self.tool_func(**resolved_args)
                 else:
                     res = self.tool_func(**resolved_args)
                 
                 separator = " | " if interrupt_msg else ""
                 interrupt_msg = f"{interrupt_msg}{separator}Tool Context: {res}"
                     
             except Exception as e:
                 logger.error(f"Error running interrupt tool: {e}")
                 interrupt_msg += f" (Tool Error: {e})"
        
        if not interrupt_msg:
            interrupt_msg = f"Waiting for input at {self.name}"

        logger.info(f"InterruptAgent '{self.name}' pausing workflow. Message: {interrupt_msg}")
        
        # Emit an event sayings we are pausing
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=f"PAUSED: {interrupt_msg}")],
            ),
             custom_metadata={
                "status": "paused",
                "interaction_mode": self.interaction_mode,
                "resume_key": self.output_key
            }
        )
        
        # Raise exception to stop the Runner
        raise WorkflowInterruption(
            agent_name=self.name,
            message=interrupt_msg,
            mode=self.interaction_mode,
            resume_key=self.output_key
        )
