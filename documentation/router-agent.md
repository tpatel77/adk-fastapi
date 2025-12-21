Router Agent

What it does (layman)
Chooses exactly one next agent based on a condition (like an if/else switch).

How to configure
- `type: router`
- `condition`: Python expression evaluated with state as variables.
- `routes`: Map of condition results (stringified) to agent names.

Variants and capabilities
- Boolean routing: return `True`/`False` to choose a branch.
- Multi-branch routing: return custom values (e.g., `"priority"`).
- Supports `{var}` placeholders in the condition; they are stripped to allow variable access.

Example
```yaml
- name: extract_document_router
  type: router
  condition: "metadata.get('type') == 'test'"
  routes:
    "True": process_content
    "False": generate_summary
```
