from typing import Any

from adk.tools.registry import register_tool


@register_tool("add_numbers")
def add_numbers(a: int, b: int) -> int:
    """Add two integers and return the sum."""
    print(f"Adding {a} and {b}")
    return a + b


@register_tool("multiply_numbers")
def multiply_numbers(a: int, b: int) -> int:
    """Multiply two integers and return the product."""
    print(f"Multiplying {a} and {b}")
    return a * b
