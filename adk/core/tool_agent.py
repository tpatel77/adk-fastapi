"""Custom ToolAgent for direct tool execution in workflows."""

import inspect
import re
import time
from typing import Any, Callable, AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.agents.callback_context import CallbackContext
from google.adk.tools.tool_context import ToolContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import Field
from adk.core.callbacks.registry import CallbackRegistry, callback_origin
from adk.core.trace import create_trace_event


class ToolAgent(BaseAgent):
    """
    A custom agent that directly executes a tool without LLM reasoning.
    """
    
    # Pydantic fields for the agent configuration
    tool_func: Callable[..., Any] = Field(..., description="The tool function to execute")
    arguments: dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")
    output_key: str | None = Field(None, description="Key to store result in session state")
    callbacks: Any | None = Field(None, description="Lifecycle callbacks (LifecycleCallbacks object)")
    
    model_config = {"arbitrary_types_allowed": True}
    
    def _resolve_arguments(self, state: dict[str, Any]) -> dict[str, Any]:
        """Resolve argument placeholders using session state."""
        resolved = {}
        
        for key, value in self.arguments.items():
            if isinstance(value, str):
                # Find all {placeholder} patterns and replace with state values
                def replace_placeholder(match: re.Match[str]) -> str:
                    state_key = match.group(1)
                    state_value = state.get(state_key, match.group(0))
                    return str(state_value) if state_value is not None else ""
                
                resolved[key] = re.sub(r'\{(\w+)\}', replace_placeholder, value)
            else:
                resolved[key] = value
        
        return resolved

    async def _run_callbacks(
        self, 
        phase_names: list[str], 
        ctx: InvocationContext, 
        **kwargs
    ) -> EventActions:
        """Execute callbacks and return collected actions (state deltas)."""
        actions = EventActions()
        
        if not phase_names:
            return actions

        cb_ctx = CallbackContext(ctx, event_actions=actions)
        tool_ctx = ToolContext(
            ctx,
            function_call_id=f"tool_agent:{ctx.invocation_id}:{self.name}",
            event_actions=actions,
        )
        
        for name in phase_names:
            func = CallbackRegistry.get(name)
            if func:
                try:
                    # Pass context if the callback accepts it
                    # Simple heuristic: try passing context, fallback if fails?
                    # Or assume all registered callbacks MUST accept context if they want persistence?
                    # We'll pass it as a keyword arg 'context'
                    # We also pass 'data' or similar for backward compat
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
                        result = func(context=tool_ctx, **kwargs)
                    else:
                        # Fallback for old logging callbacks
                        result = func(**kwargs)
                        
                    if result and isinstance(result, EventActions):
                        # Merge actions if returned directly (advanced usage)
                        # But typically modifications happen on cb_ctx
                        pass 
                except Exception as e:
                    print(f"Error in callback '{name}': {e}")

            if ctx.session is None or ctx.session_service is None:
                continue

            audit_event = Event(
                invocation_id=ctx.invocation_id,
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text="")]),
                custom_metadata={
                    "source": "callback",
                    "callback_name": name,
                    "callback_origin": callback_origin(name),
                    "callback_event_type": kwargs.get("event_type"),
                    "tool_name": kwargs.get("tool_name"),
                    "agent_name": self.name,
                    "tool_call_id": getattr(tool_ctx, "function_call_id", None),
                },
            )

            try:
                await ctx.session_service.append_event(session=ctx.session, event=audit_event)
            except Exception:
                continue
                    
        return actions

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        """Execute the tool and yield the result as an event."""
        # Get current state
        state = dict(ctx.session.state) if ctx.session else {}

        tool_name_for_trace = getattr(self.tool_func, "__name__", None) or self.name
        start_ns = time.perf_counter_ns()
        yield create_trace_event(
            invocation_context=ctx,
            phase="tool_start",
            workflow_name=ctx.app_name,
            agent_name=self.name,
            agent_type="tool",
            tool_name=tool_name_for_trace,
            status="running",
            author=self.name,
        )

        def _merge_actions(dst: EventActions, src: EventActions) -> None:
            if src is None:
                return
            if src.skip_summarization is not None:
                dst.skip_summarization = src.skip_summarization
            if src.escalate is not None:
                dst.escalate = src.escalate
            if src.transfer_to_agent is not None:
                dst.transfer_to_agent = src.transfer_to_agent
            if src.end_of_agent is not None:
                dst.end_of_agent = src.end_of_agent

            if getattr(src, "state_delta", None):
                dst.state_delta.update(src.state_delta)
            if getattr(src, "artifact_delta", None):
                dst.artifact_delta.update(src.artifact_delta)
            if getattr(src, "requested_auth_configs", None):
                dst.requested_auth_configs.update(src.requested_auth_configs)
            if getattr(src, "requested_tool_confirmations", None):
                dst.requested_tool_confirmations.update(src.requested_tool_confirmations)
        
        def _dedupe_callback_names(names: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for n in names:
                if n in seen:
                    continue
                seen.add(n)
                out.append(n)
            return out

        # 1. Run on_tool_start Callbacks (default first)
        start_actions = EventActions()
        tool_name = getattr(self.tool_func, "__name__", None) or self.name
        on_tool_start = _dedupe_callback_names(
            ["default_tool_start"] + (list(self.callbacks.on_tool_start) if self.callbacks else [])
        )
        start_actions = await self._run_callbacks(
            on_tool_start,
            ctx,
            tool_name=tool_name,
            event_type="tool_start",
        )
            # If start callbacks modified state, we should ideally emit an event or merge it.
            # We'll merge it into the final event for simplicity (batching state updates),
            # OR emit a separate event if we want distinct history entries. 
            # For ADK compliance, usually 1 invocation = 1 main event.
        
        # Resolve arguments with state values (potentially updated by callbacks?)
        # If callbacks updated state, ctx.session.state might be updated in memory by CallbackContext?
        # CallbackContext updates 'event_actions.state_delta' AND 'invocation_context.session.state' if implemented recursively?
        # Check CallbackContext impl: `self._state = State(..., delta=...)`. It doesn't write back to session immediately.
        # But we want arguments to reflect callback updates? 
        # For now, simplistic approach: arguments resolved from original state.
        
        resolved_args = self._resolve_arguments(state)
        
        # Execute the tool
        tool_actions = EventActions()
        tool_ctx = ToolContext(
            ctx,
            function_call_id=f"tool_agent:{ctx.invocation_id}:{self.name}",
            event_actions=tool_actions,
        )
        try:
            import asyncio

            call_kwargs = dict(resolved_args)
            try:
                sig = inspect.signature(self.tool_func)
                if "tool_context" in sig.parameters:
                    call_kwargs["tool_context"] = tool_ctx
            except Exception:
                pass

            if asyncio.iscoroutinefunction(self.tool_func):
                result = await self.tool_func(**call_kwargs)
            else:
                result = self.tool_func(**call_kwargs)
            result_str = str(result) if result is not None else ""
        except Exception as e:
            duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
            yield create_trace_event(
                invocation_context=ctx,
                phase="tool_error",
                workflow_name=ctx.app_name,
                agent_name=self.name,
                agent_type="tool",
                tool_name=tool_name_for_trace,
                loop_name=None,
                loop_iteration=None,
                status="error",
                duration_ms=duration_ms,
                error_type=type(e).__name__,
                error_message=str(e),
                author=self.name,
            )
            raise
        
        # 2. Run on_tool_finish Callbacks (default last)
        finish_actions = EventActions()
        on_tool_finish = _dedupe_callback_names(
            (list(self.callbacks.on_tool_finish) if self.callbacks else []) + ["default_tool_finish"]
        )
        finish_actions = await self._run_callbacks(
            on_tool_finish,
            ctx,
            tool_name=tool_name,
            result=result_str,
            event_type="tool_finish",
        )
        
        # Prepare event content
        content = types.Content(
            role="model",
            parts=[types.Part(text=result_str)],
        )
        
        # Prepare final actions: output_key delta + callback deltas
        final_actions = EventActions()

        _merge_actions(final_actions, start_actions)
        _merge_actions(final_actions, tool_actions)
        _merge_actions(final_actions, finish_actions)

        if ctx.session and final_actions.state_delta:
            ctx.session.state.update(final_actions.state_delta)

        # Merge output_key delta
        if self.output_key:
            if ctx.session:
                ctx.session.state[self.output_key] = result_str

            final_actions.state_delta[self.output_key] = result_str
        
        # Yield the result as an event
        yield Event(
            author=self.name,
            content=content,
            actions=final_actions
        )

        duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
        yield create_trace_event(
            invocation_context=ctx,
            phase="tool_finish",
            workflow_name=ctx.app_name,
            agent_name=self.name,
            agent_type="tool",
            tool_name=tool_name_for_trace,
            status="ok",
            duration_ms=duration_ms,
            author=self.name,
        )
