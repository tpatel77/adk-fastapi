A2A Agent

What it does (layman)
Talks to another agent over HTTP using a standard A2A envelope format.
It wraps the state in a protocol message and expects a standard response.

How to configure
- `type: a2a`
- `url`: Target endpoint that speaks `a2a/1.0`.
- `target_agent_id`: Identifier of the remote agent.
- `output_key`: Where to store the response.

Variants and capabilities
- Standardized envelope with `protocol`, `id`, `source`, `target`, and `payload`.
- Useful when the remote system is another agent service.

Example
```yaml
- name: billing_a2a
  type: a2a
  url: "https://agent-hub.example.com/a2a"
  target_agent_id: "billing-agent"
  output_key: billing_result
```
