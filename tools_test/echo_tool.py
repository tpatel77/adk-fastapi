import json
import os
from typing import Any

from adk.tools.registry import register_tool
from google.adk.tools.tool_context import ToolContext


@register_tool("echo_tool")
def echo_tool(message: str) -> str:
    """
    Simple echo tool for testing.
    
    Args:
        message: The message to echo
        
    Returns:
        The same message
    """
    # x = {
    #     "patient_id": "12345",
    #     "pa_question": "Does the patient have a history of diabetes?",
    #     "context": "Requesting PA for a diabetes medication."
    # }
    capital_state = "New York"
    print(f"Echoing message: {message}")
    # print(f"Echoing message: {x}")
    return capital_state


def exit_when_contains(
    state: dict[str, Any], *, key: str = "capital_city", substring: str = "Albany"
) -> bool:
    value = state.get(key)
    if value is None:
        return False
    return substring in str(value)


@register_tool("echo_tool2")
def echo_tool2(message: str) -> str:
    """
    Simple echo tool for testing.
    
    Args:
        message: The message to echo
        
    Returns:
        The same message
    """
    # x = {
    #     "patient_id": "12345",
    #     "pa_question": "Does the patient have a history of diabetes?",
    #     "context": "Requesting PA for a diabetes medication."
    # }
    capital_state = "New Jersey"
    print(f"Echoing message: {message}")
    # print(f"Echoing message: {x}")
    return capital_state


@register_tool("loop_exit_check")
def loop_exit_check(tool_context: ToolContext, key: str = "capital_city") -> str:
    value = tool_context.state.get(key)
    if value is not None:
        tool_context.actions.escalate = True
        return f"exit:true:{key}"
    return f"exit:false:{key}"