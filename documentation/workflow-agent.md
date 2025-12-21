Sub-Workflow Agent

What it does (layman)
Loads another workflow YAML file and runs it as a single agent inside the current workflow.

How to configure
- `type: workflow`
- `path`: Path to another workflow YAML.
- `description`: Optional override for this wrapper agent.

Variants and capabilities
- Nest full workflows to keep large pipelines modular.
- Reuse a common workflow across multiple entry points.
- The sub-workflow root agent name is overridden to match this agent name.

Example
```yaml
- name: compliance_subflow
  type: workflow
  path: "rag/document_processor.yaml"
```
