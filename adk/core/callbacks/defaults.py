from adk.core.callbacks.registry import register_callback


@register_callback("default_agent_start")
def default_agent_start(event_type: str | None = None, agent_name: str | None = None, data=None, **kwargs):
    return


@register_callback("default_agent_finish")
def default_agent_finish(event_type: str | None = None, agent_name: str | None = None, data=None, **kwargs):
    return


@register_callback("default_tool_start")
def default_tool_start(tool_name: str | None = None, event_type: str | None = None, data=None, **kwargs):
    return


@register_callback("default_tool_finish")
def default_tool_finish(tool_name: str | None = None, event_type: str | None = None, data=None, **kwargs):
    return


@register_callback("default_model_start")
def default_model_start(event_type: str | None = None, data=None, **kwargs):
    return


@register_callback("default_model_finish")
def default_model_finish(event_type: str | None = None, data=None, **kwargs):
    return
