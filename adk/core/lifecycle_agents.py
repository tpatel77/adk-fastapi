"""Standard lifecycle agents for workflow execution."""

from typing import AsyncGenerator, Any
import importlib

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types
from pydantic import Field
import re


class StartAgent(BaseAgent):
    """
    Standard agent that runs at the beginning of every workflow.
    Responsible for:
    - Initializing session state from provided initial_state
    - Logging start events
    """
    
    initial_state: dict[str, Any] = Field(default_factory=dict)
    
    def __init__(self, name: str = "workflow_start", initial_state: dict[str, Any] | None = None):
        super().__init__(
            name=name, 
            description="Standard workflow entry point",
            initial_state=initial_state or {}
        )

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        # Apply initial state to session
        state_delta = {}
        if self.initial_state and ctx.session:
            for key, value in self.initial_state.items():
                ctx.session.state[key] = value
                state_delta[key] = value
        
        # Emit event with state initialization
        event_args = {
            "author": self.name,
            "content": types.Content(
                role="model",
                parts=[types.Part(text="Workflow execution started.")],
            )
        }
        
        if state_delta:
            event_args["actions"] = EventActions(state_delta=state_delta)
            
        yield Event(**event_args)


class ExitAgent(BaseAgent):
    """
    Standard agent that runs at the end of every workflow.
    Responsible for:
    - Emitting the first found output_key from a list (for router branches)
    - Optionally emitting full state if configured
    """
    
    emit_full_state: bool = Field(default=False)
    output_key: str | None = Field(default=None)
    output_keys: list[str] = Field(default_factory=list)  # For router branches
    
    def __init__(
        self, 
        name: str = "workflow_exit", 
        emit_full_state: bool = False,
        output_key: str | None = None,
        output_keys: list[str] | None = None
    ):
        super().__init__(
            name=name, 
            description="Standard workflow exit point",
            emit_full_state=emit_full_state,
            output_key=output_key,
            output_keys=output_keys or []
        )

    async def _run_async_impl(
        self,
        ctx: InvocationContext,
    ) -> AsyncGenerator[Event, None]:
        output_text = "Workflow execution completed."
        
        if ctx.session and ctx.session.state:
            if self.emit_full_state:
                # Emit entire state
                import json
                output_text = json.dumps(ctx.session.state, indent=2, default=str)
            elif self.output_keys:
                # Check multiple candidate keys in order (for router branches)
                for key in self.output_keys:
                    value = ctx.session.state.get(key)
                    if value is not None:
                        output_text = str(value) if not isinstance(value, str) else value
                        break
            elif self.output_key:
                # Emit specified single output_key
                value = ctx.session.state.get(self.output_key)
                if value is not None:
                    output_text = str(value) if not isinstance(value, str) else value
            else:
                # Fallback: Use the last key added to state
                if ctx.session.state:
                    all_keys = list(ctx.session.state.keys())
                    # Skip system keys from initial_state
                    user_keys = [k for k in all_keys if k not in ('document', 'metadata')]
                    if user_keys:
                        last_key = user_keys[-1]
                        value = ctx.session.state.get(last_key)
                        if value is not None:
                            output_text = str(value) if not isinstance(value, str) else value
        
        yield Event(
            author=self.name,
            content=types.Content(
                role="model",
                parts=[types.Part(text=output_text)],
            ),
        )


class LoopInitializationAgent(BaseAgent):
    """
    Initialize a loop counter in the session state.
    """
    loop_index_key: str = Field(...)
    
    def __init__(self, name: str, loop_index_key: str):
        super().__init__(
            name=name,
            description="Initialize loop counter",
            loop_index_key=loop_index_key
        )
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        # Initialize to -1 so first increment (at start of loop) makes it 0
        state_delta = {self.loop_index_key: -1}
        if ctx.session:
            ctx.session.state[self.loop_index_key] = -1
        
        yield Event(
            author=self.name,
            content=types.Content(role="model", parts=[types.Part(text="Loop initialized")]),
            actions=EventActions(state_delta=state_delta)
        )


class LoopIncrementAgent(BaseAgent):
    """
    Increment a loop counter in the session state.
    """
    loop_index_key: str = Field(...)
    
    def __init__(self, name: str, loop_index_key: str):
        super().__init__(
            name=name,
            description="Increment loop counter",
            loop_index_key=loop_index_key
        )
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if ctx.session:
            current = ctx.session.state.get(self.loop_index_key, -1)
            new_val = current + 1
            ctx.session.state[self.loop_index_key] = new_val
            
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text=f"Iteration {new_val}")]),
                actions=EventActions(state_delta={self.loop_index_key: new_val})
            )
        else:
             yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text="No session found to increment")]),
            )


class LoopExitConditionAgent(BaseAgent):
    condition: str | None = Field(default=None)
    condition_fn: str | None = Field(default=None)
    condition_fn_args: dict[str, Any] = Field(default_factory=dict)

    def __init__(
        self,
        name: str,
        *,
        condition: str | None = None,
        condition_fn: str | None = None,
        condition_fn_args: dict[str, Any] | None = None,
    ):
        super().__init__(
            name=name,
            description="Loop exit condition",
            condition=condition,
            condition_fn=condition_fn,
            condition_fn_args=condition_fn_args or {},
        )

    def _load_condition_fn(self):
        if not self.condition_fn:
            return None
        if ":" not in self.condition_fn:
            raise ValueError(
                "exit_condition_fn must be in the form 'module.submodule:function_name'"
            )
        module_path, func_name = self.condition_fn.split(":", 1)
        mod = importlib.import_module(module_path)
        fn = getattr(mod, func_name)
        if not callable(fn):
            raise ValueError(f"exit_condition_fn '{self.condition_fn}' is not callable")
        return fn

    def _evaluate_expr(self, state: dict[str, Any]) -> bool:
        if not self.condition:
            return False

        def has(k: str) -> bool:
            return k in state and state.get(k) is not None

        def get(k: str, default: Any = None) -> Any:
            return state.get(k, default)

        def contains(container: Any, item: Any) -> bool:
            try:
                return item in container
            except Exception:
                return False

        helpers = {
            "has": has,
            "get": get,
            "contains": contains,
            "len": len,
            "any": any,
            "all": all,
        }

        clean_condition = re.sub(r"\{(\w+)\}", r"\1", self.condition)
        return bool(eval(clean_condition, {"__builtins__": {}}, {**helpers, **state}))

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = dict(ctx.session.state) if ctx.session else {}

        should_exit = False
        if self.condition_fn:
            fn = self._load_condition_fn()
            if fn is not None:
                should_exit = bool(fn(state, **(self.condition_fn_args or {})))
        elif self.condition:
            should_exit = self._evaluate_expr(state)

        if should_exit:
            yield Event(
                author=self.name,
                content=types.Content(role="model", parts=[types.Part(text="")]),
                actions=EventActions(escalate=True),
            )
