Fan-Out Router Agent

What it does (layman)
Checks multiple conditions and runs all matching agents in parallel. Optionally aggregates their outputs.

How to configure
- `type: fan_out_router`
- `routing_rules`: List of `{condition, target}` rules.
- `default_route`: Optional fallback agent if no rules match.
- `fan_in_strategy`: Optional aggregation strategy: `list` or `dict`.
- `output_key`: Where aggregated output is stored (required for fan-in).

Variants and capabilities
- Multi-match routing: more than one rule can trigger.
- Default route when nothing matches.
- Fan-in aggregation:
  - `list`: `[output1, output2, ...]` in selection order.
  - `dict`: `{agent_name: output}`.

Example
```yaml
- name: fan_out_test_agent
  type: fan_out_router
  routing_rules:
    - condition: "len(metadata) > 0"
      target: generate_summary2
    - condition: "False"
      target: generate_summary3
  default_route: generate_summary3
  fan_in_strategy: dict
  output_key: fan_out_results
```
