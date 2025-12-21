Parallel Agent

What it does (layman)
Runs multiple agents at the same time. This is useful when steps are independent.

How to configure
- `type: parallel`
- `sub_agents`: List of agent names to run concurrently.
- `description`: Optional description.

Variants and capabilities
- Use multiple tools or LLMs in parallel to speed up the workflow.
- Combine with sub-agent `output_key` values to gather results.

Example
```yaml
- name: parallel_checks
  type: parallel
  sub_agents: [grammar_check, sentiment_check]
```
