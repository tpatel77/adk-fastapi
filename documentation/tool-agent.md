Tool Agent

What it does (layman)
Calls a Python function directly (no LLM reasoning) and stores the result.

How to configure
- `type: tool`
- `tool_name`: The registered tool name from `tools:`.
- `arguments`: Arguments to pass to the tool. Supports `{state_key}` placeholders.
- `output_key`: Where to save the tool's result.
- `context`: Optional lifecycle callbacks.

Variants and capabilities
- Pure execution step for deterministic logic (math, validation, parsing).
- Arguments can reference state values at runtime.
- Can trigger tool-level callbacks for logging or auditing.

Example
```yaml
- name: add_numbers_agent
  type: tool
  tool_name: add_numbers
  arguments:
    a: "{metadata.a}"
    b: "{metadata.b}"
  output_key: sum
```
