"""
Context-aware LlmAgent that supports hooks and callbacks.
"""

import inspect
import time
from typing import AsyncGenerator, Any
from pydantic import Field

from google.adk.agents import LlmAgent, BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.adk.events.event_actions import EventActions as AdkEventActions
from google.adk.agents.callback_context import CallbackContext

from adk.config.schema import AgentContextConfig
from adk.core.callbacks.registry import CallbackRegistry, callback_origin, split_callback_names
from adk.core.trace import create_trace_event
from adk.core.callbacks.wrappers import set_current_invocation_context, reset_current_invocation_context

class ContextAwareLlmAgent(LlmAgent):
    """
    Subclass of LlmAgent that adds support for context hooks and callbacks.
    Inheritance is required to pass ADK's strict type checks.
    """
    
    agent_context_config: AgentContextConfig | None = Field(None, description="Context configuration")
    workflow_name: str | None = Field(None, description="Workflow name for trace events")
    
    def __init__(
        self,
        *args,
        context_config: AgentContextConfig = None,
        workflow_name: str | None = None,
        **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.agent_context_config = context_config
        self.workflow_name = workflow_name
        
    def _sync_state_to_session(self, ctx: InvocationContext):
        """Sync relevant state from Config to Session."""
        if not ctx.session or not self.agent_context_config:
            return
            
        # Push initial configuration to session state
        if self.agent_context_config.initial:
             for k, v in self.agent_context_config.initial.items():
                 if k not in ctx.session.state:
                     ctx.session.state[k] = v
                 
    def _execute_hook(self, hook, ctx: InvocationContext):
        """Execute a context hook."""
        if not hook or not hook.set:
            return
        
        for key, value in hook.set.items():
            if ctx.session:
                 ctx.session.state[key] = value

    async def _execute_callbacks(
        self, callback_names: list[str], ctx: InvocationContext, event_type: str
    ) -> tuple[AdkEventActions, list[Event]]:
        """Execute callbacks and return actions + audit events."""
        from google.genai import types

        actions = AdkEventActions()
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
        start_ns = time.perf_counter_ns()

        async def _run_default_agent_callback(event_type: str) -> AdkEventActions:
            actions = AdkEventActions()
            cb_ctx = CallbackContext(ctx, event_actions=actions)
            name = "default_agent_start" if event_type == "agent_start" else "default_agent_finish"
            func = CallbackRegistry.get(name)
            if not func:
                return actions
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
            return actions

        default_start_actions = await _run_default_agent_callback("agent_start")
        from google.adk.events import Event
        from google.genai import types

        start_event_kwargs = {
            "author": self.name,
            "content": types.Content(role="model", parts=[types.Part(text="")]),
            "custom_metadata": {
                "source": "callback",
                "callback_event_type": "agent_start",
                "agent_name": self.name,
                "callback_origin": "default",
                "callback_names": ["default_agent_start"],
                "callback_names_default": ["default_agent_start"],
                "callback_names_workflow_custom": [],
            },
        }
        if default_start_actions.state_delta or default_start_actions.artifact_delta:
            start_event_kwargs["actions"] = default_start_actions
        yield Event(**start_event_kwargs)

        yield create_trace_event(
            invocation_context=ctx,
            phase="agent_start",
            workflow_name=self.workflow_name,
            agent_name=self.name,
            agent_type="llm",
            status="running",
            author=self.name,
        )

        try:
            if not self.agent_context_config:
                token = set_current_invocation_context(ctx)
                try:
                    async for event in super()._run_async_impl(ctx):
                        yield event
                finally:
                    reset_current_invocation_context(token)

                default_finish_actions = await _run_default_agent_callback("agent_finish")
                from google.adk.events import Event
                from google.genai import types

                finish_event_kwargs = {
                    "author": self.name,
                    "content": types.Content(role="model", parts=[types.Part(text="")]),
                    "custom_metadata": {
                        "source": "callback",
                        "callback_event_type": "agent_finish",
                        "agent_name": self.name,
                        "callback_origin": "default",
                        "callback_names": ["default_agent_finish"],
                        "callback_names_default": ["default_agent_finish"],
                        "callback_names_workflow_custom": [],
                    },
                }
                if default_finish_actions.state_delta or default_finish_actions.artifact_delta:
                    finish_event_kwargs["actions"] = default_finish_actions
                yield Event(**finish_event_kwargs)

                duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
                yield create_trace_event(
                    invocation_context=ctx,
                    phase="agent_finish",
                    workflow_name=self.workflow_name,
                    agent_name=self.name,
                    agent_type="llm",
                    status="ok",
                    duration_ms=duration_ms,
                    author=self.name,
                )
                return

            # Sync Initial State
            self._sync_state_to_session(ctx)

            # Pre-execution Hook
            if self.agent_context_config.pre_hook:
                self._execute_hook(self.agent_context_config.pre_hook, ctx)

            # Agent Start Callback
            if (
                self.agent_context_config.callbacks
                and self.agent_context_config.callbacks.on_agent_start
            ):
                from google.adk.events import Event
                from google.genai import types

                actions, audit_events = await self._execute_callbacks(
                    self.agent_context_config.callbacks.on_agent_start,
                    ctx,
                    "agent_start",
                )
                for ev in audit_events:
                    yield ev

                if actions.state_delta or actions.artifact_delta:
                    split_names = split_callback_names(list(self.agent_context_config.callbacks.on_agent_start))
                    yield Event(
                        author=self.name,
                        content=types.Content(role="model", parts=[types.Part(text="")]),
                        actions=actions,
                        custom_metadata={
                            "source": "callback",
                            "callback_event_type": "agent_start",
                            "agent_name": self.name,
                            "callback_names": list(
                                self.agent_context_config.callbacks.on_agent_start
                            ),
                            "callback_names_default": split_names["default"],
                            "callback_names_workflow_custom": split_names["workflow_custom"],
                        },
                    )

            # Run inner logic (Standard LlmAgent execution)
            try:
                token = set_current_invocation_context(ctx)
                try:
                    async for event in super()._run_async_impl(ctx):
                        yield event
                finally:
                    reset_current_invocation_context(token)
            finally:
                # Agent Finish Callback
                if (
                    self.agent_context_config.callbacks
                    and self.agent_context_config.callbacks.on_agent_finish
                ):
                    from google.adk.events import Event
                    from google.genai import types

                    actions, audit_events = await self._execute_callbacks(
                        self.agent_context_config.callbacks.on_agent_finish,
                        ctx,
                        "agent_finish",
                    )
                    for ev in audit_events:
                        yield ev

                    if actions.state_delta or actions.artifact_delta:
                        split_names = split_callback_names(list(self.agent_context_config.callbacks.on_agent_finish))
                        yield Event(
                            author=self.name,
                            content=types.Content(
                                role="model", parts=[types.Part(text="")]
                            ),
                            actions=actions,
                            custom_metadata={
                                "source": "callback",
                                "callback_event_type": "agent_finish",
                                "agent_name": self.name,
                                "callback_names": list(
                                    self.agent_context_config.callbacks.on_agent_finish
                                ),
                                "callback_names_default": split_names["default"],
                                "callback_names_workflow_custom": split_names["workflow_custom"],
                            },
                        )

            default_finish_actions = await _run_default_agent_callback("agent_finish")
            from google.adk.events import Event
            from google.genai import types

            finish_event_kwargs = {
                "author": self.name,
                "content": types.Content(role="model", parts=[types.Part(text="")]),
                "custom_metadata": {
                    "source": "callback",
                    "callback_event_type": "agent_finish",
                    "agent_name": self.name,
                    "callback_origin": "default",
                    "callback_names": ["default_agent_finish"],
                    "callback_names_default": ["default_agent_finish"],
                    "callback_names_workflow_custom": [],
                },
            }
            if default_finish_actions.state_delta or default_finish_actions.artifact_delta:
                finish_event_kwargs["actions"] = default_finish_actions
            yield Event(**finish_event_kwargs)

            # Post-execution Hook
            if self.agent_context_config.post_hook:
                self._execute_hook(self.agent_context_config.post_hook, ctx)

            duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
            yield create_trace_event(
                invocation_context=ctx,
                phase="agent_finish",
                workflow_name=self.workflow_name,
                agent_name=self.name,
                agent_type="llm",
                status="ok",
                duration_ms=duration_ms,
                author=self.name,
            )
        except Exception as e:
            default_finish_actions = await _run_default_agent_callback("agent_finish")
            from google.adk.events import Event
            from google.genai import types

            finish_event_kwargs = {
                "author": self.name,
                "content": types.Content(role="model", parts=[types.Part(text="")]),
                "custom_metadata": {
                    "source": "callback",
                    "callback_event_type": "agent_finish",
                    "agent_name": self.name,
                    "callback_origin": "default",
                    "callback_names": ["default_agent_finish"],
                    "callback_names_default": ["default_agent_finish"],
                    "callback_names_workflow_custom": [],
                },
            }
            if default_finish_actions.state_delta or default_finish_actions.artifact_delta:
                finish_event_kwargs["actions"] = default_finish_actions
            yield Event(**finish_event_kwargs)

            duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
            yield create_trace_event(
                invocation_context=ctx,
                phase="agent_error",
                workflow_name=self.workflow_name,
                agent_name=self.name,
                agent_type="llm",
                status="error",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
                author=self.name,
            )
            raise
