from datetime import datetime

from adk.core.callbacks.registry import register_callback
from google.adk.events import EventActions


def _ts() -> str:
    return datetime.now().isoformat(timespec="milliseconds")

@register_callback("log_tool_start")
def log_tool_start(tool_name: str | None = None, event_type: str | None = None, data=None, **kwargs):
    """Log when a tool starts."""
    print(f"\n[{_ts()}] [Callback] Tool '{tool_name}' Started")
    if not kwargs.get("context"):
        return
    print(f"\ncontext availabe: {kwargs.get('context')}")
    kwargs["context"].state["tool_name"] = tool_name
    if len(kwargs) > 0:
        print(f"  Args: {kwargs}")

@register_callback("log_tool_finish")
def log_tool_finish(tool_name: str | None = None, event_type: str | None = None, data=None, **kwargs):
    """Log when a tool finishes."""
    print(f"\n[{_ts()}] [Callback] Tool '{tool_name}' Finished")
    if len(kwargs) > 0:
        print(f"  Result: {kwargs}...")


@register_callback("log_agent_start")
def log_agent_start(event_type: str, agent_name: str, **kwargs):
    context = kwargs.get("context")
    print(f"\n[{_ts()}] [Callback] Agent '{agent_name}' Started ({event_type})")
    kwargs["context"].state["a"] = 12
    kwargs["context"].state["b"] = 30

    if not context:
        if len(kwargs) > 0:
            print(f"  Data: {kwargs}")
        return

@register_callback("log_agent_finish")
def log_agent_finish(event_type: str, agent_name: str, **kwargs):
    context = kwargs.get("context")
    print(f"\n[{_ts()}] [Callback] Agent '{agent_name}' Finished ({event_type})")

    if not context:
        if len(kwargs) > 0:
            print(f"  Data: {kwargs}")
        return

    output_key = "capital_city" if agent_name == "capital_city" else agent_name
    agent_output = context.state.get(output_key)
    print(f"  Output ({output_key}): {agent_output}")

@register_callback("log_model_finish")
def log_model_finish(event_type: str, data=None, **kwargs):
    print(f"\n[{_ts()}] [Callback] Model Finished ({event_type})")
    response = None
    if isinstance(data, tuple) and len(data) > 0:
        response = data[0]
        print(f"  Response: {response}")

    usage_metadata = getattr(response, "usage_metadata", None) if response is not None else None
    print(f"  usage_metadata: {usage_metadata}")
    custom_metadata = getattr(response, "custom_metadata", None) if response is not None else None
    if isinstance(custom_metadata, dict):
        usage = custom_metadata.get("litellm_usage")
        if usage is not None:
            print(f"  usage: {usage}")
        timings = custom_metadata.get("timings_ms")
        if timings is not None:
            print(f"  timings_ms: {timings}")

@register_callback("log_model_start")
def log_model_start(event_type: str, data=None, **kwargs):
    print(f"\n[{_ts()}] [Callback] Model Started ({event_type})")
    if isinstance(data, tuple) and len(data) >= 2:
        print(f"  stream: {data[1]}")