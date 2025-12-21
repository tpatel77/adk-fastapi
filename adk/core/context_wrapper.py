"""
Wrapper agent for applying context hooks.
"""

import inspect
from typing import AsyncGenerator, Any
from pydantic import Field

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions

from adk.config.schema import AgentContextConfig
from adk.core.callbacks.registry import CallbackRegistry, callback_origin, split_callback_names

class ContextWrapperAgent(BaseAgent):
    """
    Wraps an internal agent to provide Pre/Post hooks and State Management.
    """
    
    inner_agent: BaseAgent = Field(..., description="The wrapped inner agent")
    config: AgentContextConfig = Field(..., description="Context configuration")
    
    model_config = {"arbitrary_types_allowed": True}
    
    def __init__(
        self, 
        inner_agent: BaseAgent, 
        context_config: AgentContextConfig
    ):
        super().__init__(
            name=inner_agent.name, 
            description=inner_agent.description,
            inner_agent=inner_agent,
            config=context_config
        )
        
        # Initialize initial state if defined
        # Note: We cannot easily set session state here as we don't have the session yet.
        # We rely on _sync_state_to_session called at runtime.
    
    @property
    def output_key(self) -> str | None:
        """Delegate output_key to inner agent."""
        return getattr(self.inner_agent, "output_key", None)
    
    def _sync_state_to_session(self, ctx: InvocationContext):
        """Sync relevant state from Config to Session."""
        if not ctx.session:
            return
            
        # Push initial configuration to session state
        if self.config.initial:
             for k, v in self.config.initial.items():
                 # Only set if not already present? Or overwrite? 
                 # Usually initial state implies defaults.
                 if k not in ctx.session.state:
                     ctx.session.state[k] = v
                 
    def _execute_hook(self, hook, ctx: InvocationContext):
        """Execute a context hook."""
        if not hook or not hook.set:
            return
        
        for key, value in hook.set.items():
            # Sync to ADK Session State (Runtime visibility & Persistence)
            if ctx.session:
                 ctx.session.state[key] = value

    async def _execute_callbacks(
        self, callback_names: list[str], ctx: InvocationContext, event_type: str
    ) -> tuple[EventActions, list[Event]]:
        """Execute callbacks and return actions + audit events."""
        from google.adk.agents.callback_context import CallbackContext
        from google.adk.events.event_actions import EventActions
        from google.adk.events import Event
        from google.genai import types

        actions = EventActions()
        cb_ctx = CallbackContext(ctx, event_actions=actions)
        audit_events: list[Event] = []

        for name in callback_names:
            func = CallbackRegistry.get(name)
            if func:
                try:
                    accepts_context = False
                    accepts_kwargs = False
                    try:
                        sig = inspect.signature(func)
                        accepts_context = "context" in sig.parameters
                        accepts_kwargs = any(
                            p.kind == inspect.Parameter.VAR_KEYWORD
                            for p in sig.parameters.values()
                        )
                    except Exception:
                        accepts_context = False
                        accepts_kwargs = False

                    if accepts_context or accepts_kwargs:
                        func(context=cb_ctx, event_type=event_type, agent_name=self.name)
                    else:
                        func(event_type=event_type, data=(self.name,))
                except Exception as e:
                    print(f"Error in callback '{name}': {e}")

            audit_events.append(
                Event(
                    author=self.name,
                    content=types.Content(role="model", parts=[types.Part(text="")]),
                    custom_metadata={
                        "source": "callback",
                        "callback_name": name,
                        "callback_origin": callback_origin(name),
                        "callback_event_type": event_type,
                        "agent_name": self.name,
                    },
                )
            )

        return actions, audit_events

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        
        # Sync Initial State
        self._sync_state_to_session(ctx)
        
        # Pre-execution Hook
        if self.config.pre_hook:
            self._execute_hook(self.config.pre_hook, ctx)
            
        # Custom Callback: Agent Start
        if self.config.callbacks and self.config.callbacks.on_agent_start:
            from google.adk.events import Event
            from google.genai import types
            
            actions, audit_events = await self._execute_callbacks(
                self.config.callbacks.on_agent_start, ctx, "agent_start"
            )
            for ev in audit_events:
                yield ev
            
            # If start callbacks produced persistence actions, emit an event
            if actions.state_delta or actions.artifact_delta:
                 split_names = split_callback_names(list(self.config.callbacks.on_agent_start))
                 yield Event(
                     author=self.name,
                     content=types.Content(role="model", parts=[types.Part(text="")]), # Empty content for control event
                     actions=actions,
                     custom_metadata={
                         "source": "callback",
                         "callback_event_type": "agent_start",
                         "agent_name": self.name,
                         "callback_names": list(self.config.callbacks.on_agent_start),
                         "callback_names_default": split_names["default"],
                         "callback_names_workflow_custom": split_names["workflow_custom"],
                         "callback_origin": (
                             "default"
                             if split_names["default"] and not split_names["workflow_custom"]
                             else "workflow_custom"
                             if split_names["workflow_custom"] and not split_names["default"]
                             else "mixed"
                         ),
                     },
                 )
            
        # Run inner agent
        try:
            async for event in self.inner_agent._run_async_impl(ctx):
                yield event
        finally:
             # Custom Callback: Agent Finish
             if self.config.callbacks and self.config.callbacks.on_agent_finish:
                from google.adk.events import Event
                from google.genai import types
                
                actions, audit_events = await self._execute_callbacks(
                    self.config.callbacks.on_agent_finish, ctx, "agent_finish"
                )
                for ev in audit_events:
                    yield ev
                
                if actions.state_delta or actions.artifact_delta:
                     split_names = split_callback_names(list(self.config.callbacks.on_agent_finish))
                     yield Event(
                         author=self.name,
                         content=types.Content(role="model", parts=[types.Part(text="")]),
                         actions=actions,
                         custom_metadata={
                             "source": "callback",
                             "callback_event_type": "agent_finish",
                             "agent_name": self.name,
                             "callback_names": list(self.config.callbacks.on_agent_finish),
                             "callback_names_default": split_names["default"],
                             "callback_names_workflow_custom": split_names["workflow_custom"],
                             "callback_origin": (
                                 "default"
                                 if split_names["default"] and not split_names["workflow_custom"]
                                 else "workflow_custom"
                                 if split_names["workflow_custom"] and not split_names["default"]
                                 else "mixed"
                             ),
                         },
                     )

        # Post-execution Hook
        if self.config.post_hook:
            self._execute_hook(self.config.post_hook, ctx) 
