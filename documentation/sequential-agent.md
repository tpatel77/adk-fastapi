Sequential Agent

What it does (layman)
Runs a list of agents one after another, in order.
Each step can read or write the shared session state.

How to configure
- `type: sequential`
- `sub_agents`: Ordered list of agent names.
- `description`: Optional description.

Variants and capabilities
- Chain tools and LLMs for step-by-step workflows.
- Combine with `output_key` on sub-agents to pass data forward.
- Works as a wrapper around any agent types (tool, llm, router, etc.).

Example
```yaml
- name: summarization_pipeline
  type: sequential
  sub_agents: [extract_metadata, process_content, generate_summary]
```
