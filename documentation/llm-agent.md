LLM Agent

What it does (layman)
Uses a language model to read the current workflow state and produce a response.
You can give it instructions, attach tools, and save its output to state.

How to configure
- `type: llm`
- `instruction`: In this repo, this is treated as an X42 `promptId` and is encoded before sending.
- `instruction_variables`: Variables passed to the promptId payload. Values can be `{state_key}`.
- `model`: Optional override of the default model.
- `tools`: List of tool names to make available.
- `output_key`: Where to store the result in state.
- `context`: Optional state scope and lifecycle callbacks.

Variants and capabilities
- With tools: the model can call registered tools.
- With context callbacks: hook model/tool start and finish events.
- With state-driven variables: `instruction_variables` can map to live state values.

Example
```yaml
- name: capital_city
  type: llm
  instruction: x42-e8afe1df-b769-462d-b152-ac9a1bc8591a
  instruction_variables:
    country: "{metadata.country}"
  tools:
    - echo_tool
  output_key: capital_city
```
