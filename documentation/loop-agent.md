Loop Agent

What it does (layman)
Repeats a set of agents until a stop condition is met or a max iteration count is reached.
The loop index is stored in state as `<loop_name>_index`.

How to configure
- `type: loop`
- `sub_agents`: Agents to run each loop iteration.
- `max_iterations`: Optional cap (default is 10 in the factory).
- `exit_condition`: Python expression evaluated against state (e.g., `count >= 3`).
- `exit_condition_fn`: Function reference `module:function` called as `fn(state, **args)`.
- `exit_condition_fn_args`: Optional args for `exit_condition_fn`.

Variants and capabilities
- Simple counter loop with `max_iterations`.
- State-based exit using `exit_condition` (inline expression).
- Custom exit logic with `exit_condition_fn`.

Example
```yaml
- name: loop_process_and_capital
  type: loop
  max_iterations: 5
  exit_condition_fn: "tools_test.echo_tool:exit_when_contains"
  exit_condition_fn_args:
    key: "capital_city"
    substring: "Albany"
  sub_agents:
    - process_content
    - capital_city
```
