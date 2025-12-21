"""Trace-enabled LlmAgent that preserves ADK type checks."""

from __future__ import annotations

import inspect
import time
from typing import AsyncGenerator

from google.adk.agents import LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event
from google.adk.events.event_actions import EventActions
from google.genai import types
from pydantic import Field

from adk.core.callbacks.registry import CallbackRegistry
from adk.core.trace import create_trace_event
from adk.core.callbacks.wrappers import set_current_invocation_context, reset_current_invocation_context


class TraceLlmAgent(LlmAgent):
    agent_type: str = Field("llm", description="Agent type for trace and tool-call attribution")
    workflow_name: str | None = Field(None, description="Workflow name for trace events")

    def __init__(self, *args, workflow_name: str | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self.workflow_name = workflow_name

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        start_ns = time.perf_counter_ns()

        def _run_default_agent_callback(event_type: str) -> EventActions:
            actions = EventActions()
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

        start_actions = _run_default_agent_callback("agent_start")
        start_event_kwargs = {
            "invocation_id": ctx.invocation_id,
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
        if start_actions.state_delta or start_actions.artifact_delta:
            start_event_kwargs["actions"] = start_actions
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
            token = set_current_invocation_context(ctx)
            try:
                async for event in super()._run_async_impl(ctx):
                    yield event
            finally:
                reset_current_invocation_context(token)

            finish_actions = _run_default_agent_callback("agent_finish")
            finish_event_kwargs = {
                "invocation_id": ctx.invocation_id,
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
            if finish_actions.state_delta or finish_actions.artifact_delta:
                finish_event_kwargs["actions"] = finish_actions
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
        except Exception as e:
            finish_actions = _run_default_agent_callback("agent_finish")
            finish_event_kwargs = {
                "invocation_id": ctx.invocation_id,
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
            if finish_actions.state_delta or finish_actions.artifact_delta:
                finish_event_kwargs["actions"] = finish_actions
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
