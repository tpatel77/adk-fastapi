"""Pydantic models for validating YAML workflow configurations."""

from typing import Any, Literal
from pydantic import BaseModel, Field


class ToolConfig(BaseModel):
    """Configuration for a custom tool."""
    
    name: str = Field(..., description="Unique name for the tool")
    module: str = Field(..., description="Python module path containing the tool")
    function: str = Field(..., description="Function name to use as the tool")
    description: str | None = Field(None, description="Tool description for the LLM")


class ContextHook(BaseModel):
    """Configuration for context hooks."""
    set: dict[str, Any] | None = Field(None, description="Variables to set in context")

class LifecycleCallbacks(BaseModel):
    """Configuration for lifecycle callbacks."""
    on_agent_start: list[str] = Field(default_factory=list, description="Callbacks on agent start")
    on_agent_finish: list[str] = Field(default_factory=list, description="Callbacks on agent finish")
    on_model_start: list[str] = Field(default_factory=list, description="Callbacks before model generation")
    on_model_finish: list[str] = Field(default_factory=list, description="Callbacks after model generation")
    on_tool_start: list[str] = Field(default_factory=list, description="Callbacks before tool execution")
    on_tool_finish: list[str] = Field(default_factory=list, description="Callbacks after tool execution")

class AgentContextConfig(BaseModel):
    """Context configuration for an individual agent."""
    scope: Literal["agent", "workflow", "user", "global"] = Field(
        "workflow", description="Context scope for this agent's state"
    )
    initial: dict[str, Any] | None = Field(None, description="Initial state variables")
    pre_hook: ContextHook | None = Field(None, description="Actions before agent execution")
    post_hook: ContextHook | None = Field(None, description="Actions after agent execution")
    callbacks: LifecycleCallbacks | None = Field(None, description="Custom lifecycle callbacks")

class GlobalContextConfig(BaseModel):
    """Global context configuration."""
    backend: Literal["memory", "redis", "postgres"] = Field(
        "memory", description="State store backend (for variables)"
    )
    session_storage: Literal[
        "memory",
        "redis",
        "database",
        "adk_database",
        "redis_with_database",
    ] = Field("memory", description="Session persistence backend (for ADK sessions)")
    scopes: list[Literal["global", "user", "workflow", "agent"]] = Field(
        default_factory=lambda: ["workflow"], description="Enabled scopes"
    )
    initial: dict[str, Any] | None = Field(None, description="Global initial state")
    connection_string: str | None = Field(None, description="Connection string for DB/Redis")
    redis_connection_string: str | None = Field(
        None, description="Redis connection string (overrides connection_string for redis backends)"
    )
    database_connection_string: str | None = Field(
        None, description="Database connection string (overrides connection_string for database backends)"
    )
    redis_ttl_seconds: int | None = Field(
        None, description="Optional TTL for Redis session storage in seconds"
    )


class AgentConfig(BaseModel):
    """Configuration for an individual agent."""
    
    name: str = Field(..., description="Unique name for the agent")
    type: Literal["llm", "sequential", "parallel", "loop", "tool", "router", "fan_out_router", "interrupt", "workflow", "external", "a2a"] = Field(
        "llm", description="Type of agent to create"
    )
    model: str | None = Field(None, description="Model to use (overrides default)")
    instruction: str | None = Field(None, description="System instruction for LLM agents")
    instruction_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables for X42 promptId payload; values can reference session state via {key} or {nested.key}.",
    )
    description: str | None = Field(None, description="Agent description")
    output_key: str | None = Field(None, description="State key to store output")
    tools: list[str] = Field(default_factory=list, description="List of tool names to attach")
    sub_agents: list[str] = Field(default_factory=list, description="Sub-agents for workflow agents")
    
    # Loop agent specific
    max_iterations: int | None = Field(None, description="Maximum iterations for loop agents")
    exit_condition: str | None = Field(
        None,
        description="Python expression evaluated against session state to stop a loop early when true",
    )
    exit_condition_fn: str | None = Field(
        None,
        description=(
            "Python function to decide whether to stop a loop early. "
            "Specify as 'module.submodule:function_name'. Function will be called as fn(state, **exit_condition_fn_args)."
        ),
    )
    exit_condition_fn_args: dict[str, Any] | None = Field(
        None,
        description="Keyword arguments to pass into exit_condition_fn.",
    )
    
    # Tool agent specific
    tool_name: str | None = Field(None, description="Tool to execute (for tool agents)")
    arguments: dict[str, Any] | None = Field(None, description="Arguments for tool execution (supports {state_key} placeholders)")

    # Router agent specific
    condition: str | None = Field(None, description="Python condition or LLM instruction for routing")
    routes: dict[str, str] | None = Field(None, description="Map of condition results to NEXT agent names")

    # Sub-workflow specific
    path: str | None = Field(None, description="Path to sub-workflow YAML file")

    # External agent specific
    url: str | None = Field(None, description="URL for external/a2a agent")
    method: Literal["GET", "POST", "PUT", "DELETE"] | None = Field("POST", description="HTTP method")
    headers: dict[str, str] | None = Field(None, description="HTTP headers")
    
    # A2A specific
    target_agent_id: str | None = Field(None, description="Target agent ID for A2A protocol")
    
    # Fan Out Router specific
    routing_rules: list[dict[str, str]] | None = Field(
        None, 
        description="List of routing rules for fan_out_router. Each rule should have 'condition' and 'target'."
    )
    default_route: str | None = Field(None, description="Default agent to run if no rules match (or always if configured strategy requires)")
    fan_in_strategy: Literal["last", "list", "dict"] | None = Field(
        None, 
        description="Strategy to aggregate outputs. 'list' (all outputs), 'dict' (map agent name to output)."
    )

    # Interrupt Agent specific
    interaction_mode: str | None = Field(
        None, 
        description="Mode for interrupt: 'text_input', 'approval', 'tool_input', 'prompt_input'"
    )
    message: str | None = Field(None, description="Message to show to the human (for static text interrupts)")
    
    # Prompt Capability (LLM Generation)
    instruction: str | None = Field(None, description="Prompt ID or template for generating the interrupt message via LLM")
    instruction_variables: dict[str, Any] = Field(
        default_factory=dict,
        description="Variables for the instruction prompt",
    )
    model: str | None = Field(None, description="Model to use for generating the interrupt message")
    
    resume_condition: str | None = Field(None, description="Wait until this condition is true (mostly for poller, optional for HITL)")
    timeout_seconds: int | None = Field(None, description="Timeout for waiting")

    # Context specific
    context: AgentContextConfig | None = Field(None, description="Context configuration")
    
    # Context specific
    context: AgentContextConfig | None = Field(None, description="Context configuration")


class DefaultsConfig(BaseModel):
    """Default configuration values."""
    
    model: str = Field("gemini-2.5-flash", description="Default model to use")


class ExitConfig(BaseModel):
    """Configuration for the ExitAgent."""
    output_keys: list[str] = Field(
        default_factory=list, 
        description="List of possible output keys (for router branches). First found is returned."
    )
    emit_full_state: bool = Field(
        False, 
        description="If true, emit entire state as JSON instead of specific key"
    )


class LifecycleConfig(BaseModel):
    """Configuration for lifecycle agents (Start/Exit)."""
    exit: ExitConfig | None = Field(None, description="ExitAgent configuration")


class WorkflowDefinition(BaseModel):
    """Definition of the workflow structure."""
    
    type: Literal["sequential", "parallel", "loop"] = Field(
        "sequential", description="Workflow execution type"
    )
    agents: list[str] = Field(..., description="Ordered list of agent names to execute")
    max_iterations: int | None = Field(None, description="Max iterations for loop workflows")
    lifecycle: LifecycleConfig | None = Field(None, description="Lifecycle agent configuration")


class WorkflowConfig(BaseModel):
    """Root configuration model for a workflow."""
    
    name: str = Field(..., description="Unique name for the workflow")
    description: str | None = Field(None, description="Workflow description")
    defaults: DefaultsConfig = Field(
        default_factory=DefaultsConfig, description="Default configuration values"
    )
    context: GlobalContextConfig | None = Field(None, description="Context management configuration")
    tools: list[ToolConfig] = Field(
        default_factory=list, description="Custom tool definitions"
    )
    agents: list[AgentConfig] = Field(..., description="Agent definitions")
    workflow: WorkflowDefinition = Field(..., description="Workflow structure definition")

    def get_agent_by_name(self, name: str) -> AgentConfig | None:
        """Get an agent configuration by name."""
        for agent in self.agents:
            if agent.name == name:
                return agent
        return None
    
    def get_tool_by_name(self, name: str) -> ToolConfig | None:
        """Get a tool configuration by name."""
        for tool in self.tools:
            if tool.name == name:
                return tool
        return None
