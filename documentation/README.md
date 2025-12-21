Agent Types Reference

This folder documents each agent type supported by the Agent Factory in this repo.
Each file is written in layman terms and includes configuration tips and examples.

- LLM agent: `documentation/llm-agent.md`
- Sequential agent: `documentation/sequential-agent.md`
- Parallel agent: `documentation/parallel-agent.md`
- Loop agent: `documentation/loop-agent.md`
- Tool agent: `documentation/tool-agent.md`
- Router agent: `documentation/router-agent.md`
- Fan-out router agent: `documentation/fan-out-router-agent.md`
- Sub-workflow agent: `documentation/workflow-agent.md`
- External agent: `documentation/external-agent.md`
- A2A agent: `documentation/a2a-agent.md`

Shared configuration concepts

- `output_key` stores an agent's output into session state. Downstream agents can read it via `{output_key}`.
- Placeholders like `{state_key}` are resolved from session state in tools, router conditions, and external headers/URLs.
- `context` controls state scope, lifecycle callbacks, and pre/post hooks for an agent.
