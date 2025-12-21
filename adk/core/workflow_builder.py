"""Workflow builder for loading and constructing workflows from YAML configuration."""

from pathlib import Path
from typing import Any

import yaml
from google.adk.agents import BaseAgent, SequentialAgent, ParallelAgent, LoopAgent

from adk.config.schema import WorkflowConfig
from adk.core.agent_factory import AgentFactory
from adk.tools.registry import ToolRegistry, get_registry
from adk.core.trace import TraceWrapperAgent


class WorkflowBuilder:
    """
    Builder class for constructing ADK workflows from YAML configuration files.
    
    Usage:
        builder = WorkflowBuilder()
        root_agent = builder.build_from_yaml("workflows/my_workflow.yaml")
    """
    
    def __init__(self, tool_registry: ToolRegistry | None = None):
        """
        Initialize the workflow builder.
        
        Args:
            tool_registry: Optional custom tool registry (uses global if not provided)
        """
        self.tool_registry = tool_registry or get_registry()
        self.config: WorkflowConfig | None = None
        self.root_agent: BaseAgent | None = None
        self.state_manager: Any | None = None
    
    def load_config(self, yaml_path: str | Path) -> WorkflowConfig:
        """
        Load and validate a workflow configuration from a YAML file.
        
        Args:
            yaml_path: Path to the YAML configuration file
        
        Returns:
            Validated WorkflowConfig object
        """
        yaml_path = Path(yaml_path)
        
        if not yaml_path.exists():
            raise FileNotFoundError(f"Workflow configuration not found: {yaml_path}")
        
        with open(yaml_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
        
        self.config = WorkflowConfig(**raw_config)
        return self.config
    
    def _load_custom_tools(self) -> dict[str, Any]:
        """Load custom tools defined in the configuration."""
        tools: dict[str, Any] = {}
        
        if self.config is None:
            return tools
        
        # Load custom tools from config
        for tool_config in self.config.tools:
            try:
                func = self.tool_registry.load_tool_from_module(
                    module_path=tool_config.module,
                    function_name=tool_config.function,
                    tool_name=tool_config.name,
                )
                tools[tool_config.name] = func
            except (ImportError, AttributeError) as e:
                raise ImportError(
                    f"Failed to load tool '{tool_config.name}' from "
                    f"{tool_config.module}.{tool_config.function}: {e}"
                )
        
        # Add all registered tools (including built-ins)
        tools.update(self.tool_registry.get_all())
        
        return tools
    
    def build(self) -> BaseAgent:
        """
        Build the workflow from the loaded configuration.
        
        Returns:
            The root agent for the workflow
        """
        if self.config is None:
            raise ValueError("No configuration loaded. Call load_config() first.")
        
        # Load all tools
        tools = self._load_custom_tools()
        
        # Load all tools
        tools = self._load_custom_tools()
        
        # Create agent factory
        factory = AgentFactory(self.config, tools)
        
        # Create all defined agents
        for agent_config in self.config.agents:
            factory.create_agent(agent_config)
        
        # Build the root workflow agent
        workflow = self.config.workflow
        sub_agent_names = workflow.agents
        
        # Get the sub-agents for the root workflow
        created_agents = factory.get_created_agents()
        sub_agents = [created_agents[name] for name in sub_agent_names]
        
        # Create the root workflow agent
        if workflow.type == "sequential":
            self.root_agent = SequentialAgent(
                name=self.config.name,
                sub_agents=sub_agents,
                description=self.config.description or "",
            )
        elif workflow.type == "parallel":
            self.root_agent = ParallelAgent(
                name=self.config.name,
                sub_agents=sub_agents,
                description=self.config.description or "",
            )
        elif workflow.type == "loop":
            self.root_agent = LoopAgent(
                name=self.config.name,
                sub_agents=sub_agents,
                description=self.config.description or "",
                max_iterations=workflow.max_iterations or 10,
            )
        else:
            raise ValueError(f"Unknown workflow type: {workflow.type}")
        
        return self.root_agent
    
    def build_from_yaml(self, yaml_path: str | Path) -> BaseAgent:
        """
        Convenience method to load config and build workflow in one step.
        
        Args:
            yaml_path: Path to the YAML configuration file
        
        Returns:
            The root agent for the workflow
        """
        self.load_config(yaml_path)
        user_agent = self.build()
        
        # Standardize workflow with Start and Exit agents
        from adk.core.lifecycle_agents import StartAgent, ExitAgent
        
        # Create lifecycle agents (stored for later configuration)
        self._start_agent = StartAgent()
        self._exit_agent = ExitAgent()
        
        # Apply lifecycle config from YAML if present
        if self.config and self.config.workflow.lifecycle:
            lifecycle = self.config.workflow.lifecycle
            if lifecycle.exit:
                if lifecycle.exit.output_keys:
                    self._exit_agent.output_keys = lifecycle.exit.output_keys
                    self._exit_agent.emit_full_state = lifecycle.exit.emit_full_state

        traced_start = TraceWrapperAgent(
            self._start_agent,
            agent_type="lifecycle",
            workflow_name=self.config.name if self.config else None,
        )
        traced_exit = TraceWrapperAgent(
            self._exit_agent,
            agent_type="lifecycle",
            workflow_name=self.config.name if self.config else None,
        )
        
        wrapper = SequentialAgent(
            name=f"{user_agent.name}_lifecycle",
            sub_agents=[
                traced_start,
                user_agent,
                traced_exit
            ],
            description=f"Standardized lifecycle wrapper for {user_agent.name}"
        )
        return TraceWrapperAgent(
            wrapper,
            agent_type="workflow",
            workflow_name=self.config.name if self.config else None,
        )
    
    def get_config(self) -> WorkflowConfig | None:
        """Get the loaded configuration."""
        return self.config
    
    def get_root_agent(self) -> BaseAgent | None:
        """Get the built root agent."""
        return self.root_agent
    
    def get_start_agent(self):
        """Get the StartAgent for runtime configuration."""
        return getattr(self, '_start_agent', None)
    
    def get_exit_agent(self):
        """Get the ExitAgent for runtime configuration."""
        return getattr(self, '_exit_agent', None)
