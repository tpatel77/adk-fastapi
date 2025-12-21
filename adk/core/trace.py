"""Trace utilities and wrapper agent."""

from __future__ import annotations

from dataclasses import dataclass
import inspect
import time
from typing import Any, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import Field

from adk.core.callbacks.registry import CallbackRegistry


def _extract_loop_info(state: dict[str, Any]) -> tuple[Optional[str], Optional[int]]:
    index_items: list[tuple[str, Any]] = [
        (k, v) for k, v in state.items() if isinstance(k, str) and k.endswith("_index")
    ]
    if not index_items:
        return None, None

    if len(index_items) == 1:
        k, v = index_items[0]
        return k[: -len("_index")], v if isinstance(v, int) else None

    best_k: Optional[str] = None
    best_v: Optional[int] = None
    for k, v in index_items:
        if not isinstance(v, int):
            continue
        if best_v is None or v > best_v:
            best_k = k
            best_v = v

    if best_k is None:
        return None, None

    return best_k[: -len("_index")], best_v


def create_trace_event(
    *,
    invocation_context: InvocationContext,
    phase: str,
    workflow_name: Optional[str],
    agent_name: Optional[str],
    agent_type: Optional[str],
    tool_name: Optional[str] = None,
    loop_name: Optional[str] = None,
    loop_iteration: Optional[int] = None,
    status: Optional[str] = None,
    duration_ms: Optional[int] = None,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
    author: Optional[str] = None,
) -> Event:
    session = invocation_context.session
    state = dict(session.state) if session else {}

    if loop_name is None or loop_iteration is None:
        inferred_loop_name, inferred_loop_iteration = _extract_loop_info(state)
        loop_name = loop_name or inferred_loop_name
        loop_iteration = loop_iteration if loop_iteration is not None else inferred_loop_iteration

    resolved_workflow_name = workflow_name or (invocation_context.app_name if invocation_context else None)

    return Event(
        invocation_id=invocation_context.invocation_id,
        author=author or (agent_name or "trace"),
        content=None,
        custom_metadata={
            "source": "trace",
            "phase": phase,
            "workflow_name": resolved_workflow_name,
            "agent_name": agent_name,
            "agent_type": agent_type,
            "tool_name": tool_name,
            "loop_name": loop_name,
            "loop_iteration": loop_iteration,
            "status": status,
            "duration_ms": duration_ms,
            "error_type": error_type,
            "error_message": error_message,
        },
    )


class TraceWrapperAgent(BaseAgent):
    inner_agent: BaseAgent = Field(...)
    agent_type: str = Field(...)
    workflow_name: str | None = Field(default=None)

    model_config = {"arbitrary_types_allowed": True}

    def __init__(
        self,
        inner_agent: BaseAgent,
        *,
        agent_type: str,
        workflow_name: str | None = None,
    ):
        super().__init__(
            name=inner_agent.name,
            description=inner_agent.description,
            inner_agent=inner_agent,
            agent_type=agent_type,
            workflow_name=workflow_name,
        )

    @property
    def output_key(self) -> str | None:
        """Delegate output_key to inner agent."""
        return getattr(self.inner_agent, "output_key", None)

    async def _run_async_impl(self, ctx: InvocationContext):
        start_ns = time.perf_counter_ns()

        def _dedupe_callback_names(names: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for n in names:
                if n in seen:
                    continue
                seen.add(n)
                out.append(n)
            return out

        async def _run_default_agent_callback(event_type: str) -> EventActions:
            actions = EventActions()
            cb_ctx = CallbackContext(ctx, event_actions=actions)
            callback_names = _dedupe_callback_names(
                [
                    "default_agent_start" if event_type == "agent_start" else "default_agent_finish",
                ]
            )
            for name in callback_names:
                func = CallbackRegistry.get(name)
                if not func:
                    continue
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

        start_actions = await _run_default_agent_callback("agent_start")
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
            agent_type=self.agent_type,
            status="running",
            author=self.name,
        )

        try:
            async for event in self.inner_agent._run_async_impl(ctx):
                yield event

            finish_actions = await _run_default_agent_callback("agent_finish")
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
                agent_type=self.agent_type,
                status="ok",
                duration_ms=duration_ms,
                author=self.name,
            )
        except Exception as e:
            finish_actions = await _run_default_agent_callback("agent_finish")
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
                agent_type=self.agent_type,
                status="error",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
                author=self.name,
            )
            raise
