"""
Wrappers for Models and Tools to enable lifecycle callbacks.
"""

import asyncio
import contextvars
import inspect
import time
from typing import Any, Callable, AsyncGenerator

from pydantic import Field

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_request import LlmRequest
from google.adk.models.llm_response import LlmResponse

from adk.core.callbacks.registry import CallbackRegistry, callback_origin
from adk.core.trace import create_trace_event


_CURRENT_INVOCATION_CONTEXT: contextvars.ContextVar[Any | None] = contextvars.ContextVar(
    "adk_current_invocation_context", default=None
)


def set_current_invocation_context(ctx: Any | None) -> contextvars.Token:
    return _CURRENT_INVOCATION_CONTEXT.set(ctx)


def reset_current_invocation_context(token: contextvars.Token) -> None:
    _CURRENT_INVOCATION_CONTEXT.reset(token)


def get_current_invocation_context() -> Any | None:
    return _CURRENT_INVOCATION_CONTEXT.get()


class CallbackModelWrapper(BaseLlm):
    """Wraps an ADK BaseLlm model to trigger callbacks."""

    model: str
    inner_model: BaseLlm
    on_start: list[str] = Field(default_factory=list)
    on_finish: list[str] = Field(default_factory=list)

    def __init__(self, inner_model: BaseLlm, on_start: list[str], on_finish: list[str]):
        super().__init__(
            model=inner_model.model,
            inner_model=inner_model,
            on_start=on_start or [],
            on_finish=on_finish or [],
        )

    def __getattr__(self, name: str) -> Any:
        # Delegate other attributes (api_client, etc.) to inner model.
        return getattr(self.inner_model, name)

    async def generate_content_async(
        self, llm_request: LlmRequest, stream: bool = False
    ) -> AsyncGenerator[LlmResponse, None]:
        inv_ctx = get_current_invocation_context()
        session = getattr(inv_ctx, "session", None) if inv_ctx is not None else None
        invocation_id = getattr(inv_ctx, "invocation_id", None) if inv_ctx is not None else None
        author = getattr(getattr(inv_ctx, "agent", None), "name", None) if inv_ctx is not None else None

        self._append_callback_audit_events(
            invocation_context=inv_ctx,
            session=session,
            invocation_id=invocation_id,
            author=author,
            callback_names=self.on_start,
            callback_event_type="model_start",
        )
        self._run_callbacks(self.on_start, "start", llm_request, stream)
        last: LlmResponse | None = None
        try:
            async for item in self.inner_model.generate_content_async(
                llm_request, stream=stream
            ):
                last = item
                yield item
        finally:
            if last is not None:
                self._append_callback_audit_events(
                    invocation_context=inv_ctx,
                    session=session,
                    invocation_id=invocation_id,
                    author=author,
                    callback_names=self.on_finish,
                    callback_event_type="model_finish",
                )
                self._run_callbacks(self.on_finish, "finish", last)

    def _append_callback_audit_events(
        self,
        *,
        invocation_context: Any | None,
        session: Any | None,
        invocation_id: Any | None,
        author: str | None,
        callback_names: list[str],
        callback_event_type: str,
    ) -> None:
        if invocation_context is None or session is None or not invocation_id:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is None:
            return

        from google.adk.events import Event
        from google.genai import types

        for name in callback_names or []:
            event = Event(
                invocation_id=invocation_id,
                author=author or "model_callback",
                content=types.Content(role="model", parts=[types.Part(text="")]),
                custom_metadata={
                    "source": "callback",
                    "callback_name": name,
                    "callback_origin": callback_origin(name),
                    "callback_event_type": callback_event_type,
                    "agent_name": author,
                    "model_name": self.model,
                },
            )

            async def _append(ev: Event):
                try:
                    await invocation_context.session_service.append_event(session=session, event=ev)
                except Exception:
                    return

            loop.create_task(_append(event))

    def _run_callbacks(self, callback_names: list[str], event_type: str, *data):
        """Execute registered callbacks."""
        for name in callback_names:
            func = CallbackRegistry.get(name)
            if func:
                try:
                    func(event_type=f"model_{event_type}", data=data)
                except Exception as e:
                    print(f"Error in callback '{name}': {e}")


class CallbackToolWrapper:
    """Wraps a tool function to trigger callbacks."""
    
    def __init__(self, tool_func: Callable, name: str, on_start: list[str], on_finish: list[str]):
        self._tool_func = tool_func
        self._name = name
        self._on_start = on_start
        self._on_finish = on_finish

        self._tool_sig = inspect.signature(tool_func)

        base_sig = inspect.signature(tool_func)
        params = list(base_sig.parameters.values())
        if "tool_context" not in base_sig.parameters:
            params.append(
                inspect.Parameter(
                    "tool_context",
                    kind=inspect.Parameter.KEYWORD_ONLY,
                    default=None,
                )
            )
        self.__signature__ = base_sig.replace(parameters=params)
        
        # Mimic the wrapped function's metadata
        self.__name__ = getattr(tool_func, "__name__", "wrapped_tool")
        self.__doc__ = getattr(tool_func, "__doc__", "")

        # Proxy attributes expected by ADK's tool declaration utilities
        # (they assume a real Python function and may access __code__/__globals__/etc.)
        self.__module__ = getattr(tool_func, "__module__", None)
        self.__qualname__ = getattr(tool_func, "__qualname__", self.__name__)
        
    def __call__(self, *args, tool_context=None, **kwargs) -> Any:
        if tool_context is not None:
            kwargs["tool_context"] = tool_context
        context = self._extract_context(args, kwargs)

        inv_ctx = getattr(context, "_invocation_context", None) if context is not None else None
        session = getattr(context, "session", None) if context is not None else None
        invocation_id = getattr(context, "invocation_id", None) if context is not None else None
        author = getattr(context, "agent_name", None) or "tool_callback"
        current_agent = getattr(inv_ctx, "agent", None) if inv_ctx is not None else None
        agent_type = getattr(current_agent, "agent_type", None) or (
            type(current_agent).__name__ if current_agent is not None else None
        )

        start_ns = time.perf_counter_ns()
        if inv_ctx is not None and session is not None and invocation_id:
            trace_event = create_trace_event(
                invocation_context=inv_ctx,
                phase="tool_start",
                workflow_name=inv_ctx.app_name,
                agent_name=author,
                agent_type=agent_type,
                tool_name=self._name,
                status="running",
                author=author,
            )

            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                async def _append_start():
                    try:
                        await inv_ctx.session_service.append_event(session=session, event=trace_event)
                    except Exception:
                        return

                loop.create_task(_append_start())

        self._run_callbacks(self._on_start, "start", context, args, kwargs)
        try:
            call_kwargs = dict(kwargs)
            if "tool_context" in call_kwargs and "tool_context" not in self._tool_sig.parameters:
                # Many tools do not accept tool_context; ADK passes it separately.
                call_kwargs.pop("tool_context", None)
            result = self._tool_func(*args, **call_kwargs)
            self._run_callbacks(self._on_finish, "finish", context, result)

            if inv_ctx is not None and session is not None and invocation_id:
                duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
                finish_event = create_trace_event(
                    invocation_context=inv_ctx,
                    phase="tool_finish",
                    workflow_name=inv_ctx.app_name,
                    agent_name=author,
                    agent_type=agent_type,
                    tool_name=self._name,
                    status="ok",
                    duration_ms=duration_ms,
                    author=author,
                )

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None:
                    async def _append_finish():
                        try:
                            await inv_ctx.session_service.append_event(session=session, event=finish_event)
                        except Exception:
                            return

                    loop.create_task(_append_finish())

            return result
        except Exception as e:
            if inv_ctx is not None and session is not None and invocation_id:
                duration_ms = int((time.perf_counter_ns() - start_ns) / 1_000_000)
                err_event = create_trace_event(
                    invocation_context=inv_ctx,
                    phase="tool_error",
                    workflow_name=inv_ctx.app_name,
                    agent_name=author,
                    agent_type=agent_type,
                    tool_name=self._name,
                    status="error",
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    author=author,
                )

                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop is not None:
                    async def _append_err():
                        try:
                            await inv_ctx.session_service.append_event(session=session, event=err_event)
                        except Exception:
                            return

                    loop.create_task(_append_err())
            raise e

    @property
    def __code__(self):  # type: ignore
        return getattr(self._tool_func, "__code__")

    @property
    def __globals__(self):  # type: ignore
        return getattr(self._tool_func, "__globals__")

    @property
    def __defaults__(self):  # type: ignore
        return getattr(self._tool_func, "__defaults__", None)

    @property
    def __kwdefaults__(self):  # type: ignore
        return getattr(self._tool_func, "__kwdefaults__", None)

    @property
    def __closure__(self):  # type: ignore
        return getattr(self._tool_func, "__closure__", None)

    @property
    def __annotations__(self):  # type: ignore
        return getattr(self._tool_func, "__annotations__", {})
            
    def _extract_context(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> Any | None:
        ctx = kwargs.get("context")
        if ctx is not None:
            return ctx

        tool_ctx = kwargs.get("tool_context")
        if tool_ctx is not None:
            return tool_ctx

        try:
            from google.adk.agents.callback_context import CallbackContext
            from google.adk.tools.tool_context import ToolContext
        except Exception:
            CallbackContext = None
            ToolContext = None

        for v in list(kwargs.values()) + list(args):
            if ToolContext is not None and isinstance(v, ToolContext):
                return v
            if CallbackContext is not None and isinstance(v, CallbackContext):
                return v
        return None

    def _run_callbacks(self, callback_names: list[str], event_type: str, context: Any | None, *data):
        """Execute registered callbacks."""
        inv_ctx = getattr(context, "_invocation_context", None) if context is not None else None
        session = getattr(context, "session", None) if context is not None else None
        invocation_id = getattr(context, "invocation_id", None) if context is not None else None
        author = getattr(context, "agent_name", None) if context is not None else None

        if inv_ctx is not None and session is not None and invocation_id:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                loop = None

            if loop is not None:
                from google.adk.events import Event
                from google.genai import types

                callback_event_type = f"tool_{event_type}"
                for n in callback_names or []:
                    audit_event = Event(
                        invocation_id=invocation_id,
                        author=author or "tool_callback",
                        content=types.Content(role="model", parts=[types.Part(text="")]),
                        custom_metadata={
                            "source": "callback",
                            "callback_name": n,
                            "callback_origin": callback_origin(n),
                            "callback_event_type": callback_event_type,
                            "tool_name": self._name,
                            "agent_name": author,
                        },
                    )

                    async def _append(ev: Event):
                        try:
                            await inv_ctx.session_service.append_event(session=session, event=ev)
                        except Exception:
                            return

                    loop.create_task(_append(audit_event))

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

                    if context is not None and (accepts_context or accepts_kwargs):
                        func(
                            event_type=f"tool_{event_type}",
                            tool_name=self._name,
                            data=data,
                            context=context,
                        )
                    else:
                        func(event_type=f"tool_{event_type}", tool_name=self._name, data=data)
                except Exception as e:
                    print(f"Error in callback '{name}': {e}")
