"""Agent factory for creating ADK agents from configuration."""

from typing import Any
import re

from google.adk.agents import LlmAgent, SequentialAgent, LoopAgent, ParallelAgent, BaseAgent

from adk.config.schema import AgentConfig, WorkflowConfig
from adk.config.schema import AgentConfig, WorkflowConfig
from adk.core.tool_agent import ToolAgent
from adk.core.router_agent import RouterAgent
from adk.core.external_agent import ExternalAgent
from adk.core.a2a_agent import A2AAgent
from adk.core.a2a_agent import A2AAgent
from google.adk.models import lite_llm as adk_lite_llm
from adk.llm_gateway.x42_gateway_adk import X42GatewayADK
from adk.core.callbacks.wrappers import CallbackModelWrapper, CallbackToolWrapper
import base64
import json


# ============================================================
# GATEWAY SETUP
# ============================================================
gateway = X42GatewayADK()
gateway.url = "https://qaservices-pcw-colo-west.corp.cvscaremark.com/enterprise-capability-x42-llm-gateway/v1"
gateway.service_headers = {"x-gateway": "x42-pcw-colo-np"}




class AgentFactory:
    """Factory class for creating ADK agents from configuration."""
    
    def __init__(self, config: WorkflowConfig, tools: dict[str, Any] | None = None):
        """
        Initialize the agent factory.
        
        Args:
            config: The workflow configuration
            tools: Dictionary of available tools
        """
        self.config = config
        self.tools = tools or {}
        self._created_agents: dict[str, BaseAgent] = {}
    
    def create_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """
        Create an agent based on its configuration.
        
        Args:
            agent_config: Configuration for the agent
        
        Returns:
            The created ADK agent
        """
        # Check if already created (for reuse in sub-agents)
        if agent_config.name in self._created_agents:
            return self._created_agents[agent_config.name]
        
        agent: BaseAgent
        
        if agent_config.type == "llm":
            agent = self._create_llm_agent(agent_config)
        elif agent_config.type == "sequential":
            agent = self._create_sequential_agent(agent_config)
        elif agent_config.type == "parallel":
            agent = self._create_parallel_agent(agent_config)
        elif agent_config.type == "loop":
            agent = self._create_loop_agent(agent_config)
        elif agent_config.type == "tool":
            agent = self._create_tool_agent(agent_config)
        elif agent_config.type == "router":
            agent = self._create_router_agent(agent_config)
        elif agent_config.type == "workflow":
            agent = self._create_sub_workflow_agent(agent_config)
        elif agent_config.type == "external":
            agent = self._create_external_agent(agent_config)
        elif agent_config.type == "a2a":
            agent = self._create_a2a_agent(agent_config)
        elif agent_config.type == "fan_out_router":
            agent = self._create_fan_out_router_agent(agent_config)
        elif agent_config.type == "interrupt":
            agent = self._create_interrupt_agent(agent_config)
        else:
            raise ValueError(f"Unknown agent type: {agent_config.type}")
            
        # Apply Callbacks (Tool and Model level)
        if agent_config.context and agent_config.context.callbacks:
            cbs = agent_config.context.callbacks
            
            # Wrap Tools (if any exist on the agent)
            # ADK agents (BaseAgent) store tools in different ways or not at all (e.g. Sequential).
            # LlmAgent stores them in self.tools.
            if hasattr(agent, "tools") and agent.tools and (cbs.on_tool_start or cbs.on_tool_finish):
                pass 
                
        # Apply context wrapper (Agent level)
        # Skip this for ContextAwareLlmAgent as it handles context internally
        from google.adk.agents import LlmAgent
        is_context_aware = hasattr(agent, "agent_context_config") # Duck typing check or import class
        
        if agent_config.context and not is_context_aware:
            from adk.core.context_wrapper import ContextWrapperAgent
            agent = ContextWrapperAgent(agent, agent_config.context)

        if not isinstance(agent, LlmAgent):
            from adk.core.trace import TraceWrapperAgent
            agent = TraceWrapperAgent(
                agent,
                agent_type=agent_config.type,
                workflow_name=self.config.name,
            )
            
        self._created_agents[agent_config.name] = agent
        return agent
    
    def _create_llm_agent(self, agent_config: AgentConfig) -> LlmAgent:
        """Create an LLM agent."""
        # Get model from agent config or use default
        model_name = agent_config.model or self.config.defaults.model
        
        # Wrap Model if callbacks present
        # Note: 'model' arg in LlmAgent can be a string (name) or Model object.
        # If we want to wrap, we must instantiate the Model object first.
        # ADK usually handles string->Model resolution internally.
        # We need to access the ModelRegistry or similar if we want to wrap it.
        # Or, LlmAgent takes model_client?
        
        # Simpler approach: LlmAgent takes `model` which is usually a string.
        # If we pass a string, ADK creates the model. We can't wrap it easily unless we subclass LlmAgent.
        # Limitations of ADK wrapping?
        
        # BUT, standard Model object from google.adk.model can be passed.
        # Let's assume we can create it.
        from google.adk.models import Gemini
        model_obj = Gemini(model=model_name)

        def _get_state_value(state: dict[str, Any], path: str) -> Any:
            cur: Any = state
            for part in path.split("."):
                if not isinstance(cur, dict):
                    return None
                cur = cur.get(part)
                if cur is None:
                    return None
            return cur

        def _render_template(value: str, state: dict[str, Any]) -> Any:
            m = re.fullmatch(r"\{([^{}]+)\}", value.strip())
            if m:
                return _get_state_value(state, m.group(1))

            def repl(match: re.Match[str]) -> str:
                v = _get_state_value(state, match.group(1))
                return "" if v is None else str(v)

            return re.sub(r"\{([^{}]+)\}", repl, value)

        def _resolve_variables(template_obj: Any, state: dict[str, Any]) -> Any:
            if isinstance(template_obj, str):
                return _render_template(template_obj, state)
            if isinstance(template_obj, dict):
                return {k: _resolve_variables(v, state) for k, v in template_obj.items()}
            if isinstance(template_obj, list):
                return [_resolve_variables(v, state) for v in template_obj]
            return template_obj

        prompt_id = agent_config.instruction or ""
        variables_template = agent_config.instruction_variables or {}

        def instruction_provider(ctx) -> str:
            state = dict(getattr(ctx, "state", {}) or {})
            system_prompt = {
                "promptId": prompt_id,
                "variables": _resolve_variables(variables_template, state),
            }
            return base64.b64encode(json.dumps(system_prompt).encode()).decode()
        
        def _dedupe_callback_names(names: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for n in names:
                if n in seen:
                    continue
                seen.add(n)
                out.append(n)
            return out

        # Collect tools for this agent
        agent_tools = []
        for tool_name in agent_config.tools:
            if tool_name in self.tools:
                tool_func = self.tools[tool_name]

                cbs = agent_config.context.callbacks if agent_config.context and agent_config.context.callbacks else None
                on_tool_start = _dedupe_callback_names(
                    ["default_tool_start"] + (list(cbs.on_tool_start) if cbs else [])
                )
                on_tool_finish = _dedupe_callback_names(
                    (list(cbs.on_tool_finish) if cbs else []) + ["default_tool_finish"]
                )
                tool_func = CallbackToolWrapper(tool_func, tool_name, on_tool_start, on_tool_finish)
                
                agent_tools.append(tool_func)
        
        # Decide class based on context presence
        # if agent_config.context:
        #     from adk.core.context_llm_agent import ContextAwareLlmAgent
        #     return ContextAwareLlmAgent(
        #         name=agent_config.name,
        #         model=model_obj,
        #         instruction=agent_config.instruction or "",
        #         description=agent_config.description or "",
        #         output_key=agent_config.output_key,
        #         tools=agent_tools,
        #         context_config=agent_config.context
        #     )
        # else:
        #     return LlmAgent(
        #         name=agent_config.name,
        #         model=model_obj,
        #         instruction=agent_config.instruction or "",
        #         description=agent_config.description or "",
        #         output_key=agent_config.output_key,
        #         tools=agent_tools,
        #     )
        model = gateway.get_llm_model({"experience_id": "pa-orchestrator"})
        cbs = agent_config.context.callbacks if agent_config.context and agent_config.context.callbacks else None
        on_model_start = _dedupe_callback_names(
            ["default_model_start"] + (list(cbs.on_model_start) if cbs else [])
        )
        on_model_finish = _dedupe_callback_names(
            (list(cbs.on_model_finish) if cbs else []) + ["default_model_finish"]
        )
        model = CallbackModelWrapper(model, on_model_start, on_model_finish)

        if agent_config.context:
            from adk.core.context_llm_agent import ContextAwareLlmAgent
            return ContextAwareLlmAgent(
                name=agent_config.name,
                model=model,
                instruction=instruction_provider,
                description=agent_config.description or "",
                output_key=agent_config.output_key,
                tools=agent_tools,
                context_config=agent_config.context,
                workflow_name=self.config.name,
            )
        else:
            from adk.core.trace_llm_agent import TraceLlmAgent
            return TraceLlmAgent(
                name=agent_config.name,
                model=model,
                instruction=instruction_provider,
                description=agent_config.description or "",
                output_key=agent_config.output_key,
                tools=agent_tools,
                workflow_name=self.config.name,
            )
    
    def _create_sequential_agent(self, agent_config: AgentConfig) -> SequentialAgent:
        """Create a sequential workflow agent."""
        sub_agents = self._create_sub_agents(agent_config.sub_agents)
        
        return SequentialAgent(
            name=agent_config.name,
            sub_agents=sub_agents,
            description=agent_config.description or "",
        )
    
    def _create_parallel_agent(self, agent_config: AgentConfig) -> ParallelAgent:
        """Create a parallel workflow agent."""
        sub_agents = self._create_sub_agents(agent_config.sub_agents)
        
        return ParallelAgent(
            name=agent_config.name,
            sub_agents=sub_agents,
            description=agent_config.description or "",
        )
    
    def _create_loop_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """Create a loop workflow agent with automatic state management."""
        from adk.core.lifecycle_agents import (
            LoopInitializationAgent,
            LoopIncrementAgent,
            LoopExitConditionAgent,
        )
        from adk.core.trace import TraceWrapperAgent
        
        loop_key = f"{agent_config.name}_index"
        
        # 1. Create sub-agents
        sub_agents = self._create_sub_agents(agent_config.sub_agents)
        
        # 2. Inject Incrementer at start of loop
        increment_agent = LoopIncrementAgent(
            name=f"{agent_config.name}_increment",
            loop_index_key=loop_key
        )
        increment_agent = TraceWrapperAgent(
            increment_agent,
            agent_type="lifecycle",
            workflow_name=self.config.name,
        )

        loop_sub_agents = [increment_agent] + sub_agents
        if agent_config.exit_condition or agent_config.exit_condition_fn:
            exit_agent = LoopExitConditionAgent(
                name=f"{agent_config.name}_exit_condition",
                condition=agent_config.exit_condition,
                condition_fn=agent_config.exit_condition_fn,
                condition_fn_args=agent_config.exit_condition_fn_args,
            )
            loop_sub_agents.append(
                TraceWrapperAgent(
                    exit_agent,
                    agent_type="lifecycle",
                    workflow_name=self.config.name,
                )
            )
        
        # 3. Create the actual LoopAgent
        loop_agent = LoopAgent(
            name=f"{agent_config.name}_loop",
            sub_agents=loop_sub_agents,
            description=agent_config.description or "",
            max_iterations=agent_config.max_iterations or 10,
        )
        
        # 4. Create Initializer
        init_agent = LoopInitializationAgent(
            name=f"{agent_config.name}_init",
            loop_index_key=loop_key
        )
        init_agent = TraceWrapperAgent(
            init_agent,
            agent_type="lifecycle",
            workflow_name=self.config.name,
        )
        
        # 5. Wrap in Sequence [Init, Loop]
        # This wrapper becomes the "agent" exposed to the user/parent
        wrapper = SequentialAgent(
            name=agent_config.name,
            sub_agents=[init_agent, loop_agent],
            description=f"Managed loop {agent_config.name}"
        )
        
        return wrapper
    
        return ToolAgent(
            name=agent_config.name,
            tool_func=tool_func, # We should wrap this too if callbacks exist
            arguments=agent_config.arguments or {},
            output_key=agent_config.output_key,
            description=agent_config.description or "",
        )
        
    def _create_tool_agent(self, agent_config: AgentConfig) -> ToolAgent:
        """Create a tool agent for direct tool execution."""
        if not agent_config.tool_name:
            raise ValueError(f"Tool agent '{agent_config.name}' requires 'tool_name' to be specified")
        
        # Get the tool function
        tool_func = self.tools.get(agent_config.tool_name)
        if tool_func is None:
            raise ValueError(f"Tool not found: {agent_config.tool_name}")
            
        callbacks = None
        if agent_config.context:
            callbacks = agent_config.context.callbacks
        
        return ToolAgent(
            name=agent_config.name,
            tool_func=tool_func,
            arguments=agent_config.arguments or {},
            output_key=agent_config.output_key,
            callbacks=callbacks,
            description=agent_config.description or "",
        )

    def _create_router_agent(self, agent_config: AgentConfig) -> RouterAgent:
        """Create a router agent."""
        if not agent_config.condition:
            raise ValueError(f"Router agent '{agent_config.name}' requires 'condition'")
        if not agent_config.routes:
            raise ValueError(f"Router agent '{agent_config.name}' requires 'routes'")
        
        # We need to resolve the target agents.
        # But wait - if target agents are LATER in the list or not yet created, we have a problem.
        # ADK agents usually wrap instantiated agents.
        # So we must ensure all potential targets are created.
        
        # Strategy:
        # 1. Check if potential targets are already created.
        # 2. If not, create them now.
        
        resolved_routes = {}
        for result_key, agent_name in agent_config.routes.items():
            # Check created
            if agent_name in self._created_agents:
                resolved_routes[result_key] = self._created_agents[agent_name]
            else:
                # Find config and create
                target_config = self.config.get_agent_by_name(agent_name)
                if not target_config:
                    raise ValueError(f"Router target agent not found: {agent_name}")
                
                # Recursive creation (handles if it's already created inside create_agent)
                resolved_routes[result_key] = self.create_agent(target_config)
                
        return RouterAgent(
            name=agent_config.name,
            condition=agent_config.condition,
            routes=resolved_routes,
            description=agent_config.description or "",
        )

    def _create_sub_workflow_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """Create a sub-workflow as an agent."""
        if not agent_config.path:
            raise ValueError(f"Workflow agent '{agent_config.name}' requires 'path'")
            
        # Avoid circular import by importing here
        from adk.core.workflow_builder import WorkflowBuilder
        
        # Create a new builder for the sub-workflow
        # We pass the same tool registry to share tools
        # We might want to handle paths relative to the current workflow file?
        # For now, assume relative to cwd or absolute
        
        builder = WorkflowBuilder(tool_registry=None) # Uses global registry by default
        
        # Build the sub-workflow
        try:
            sub_agent = builder.build_from_yaml(agent_config.path)
            # We wrap it or just return it? 
            # The sub_agent is already a BaseAgent (Sequential/Process etc) using the name from YAML.
            # We might want to override the name with the one in this config?
            # ADK agents have names. If we return it as is, it has the sub-workflow's name.
            # But the parent workflow expects 'agent_config.name'.
            # ADK doesn't easily support renaming agents after creation if they are complex.
            # However, for orchestration, the name matters for ID.
            # Let's trust the sub-workflow's internal structure but maybe wrap it?
            # Actually, `sub_agents` lists refer to names. 
            # If I have `- name: sub_flow`, I expect `sub_flow` to be the agent.
            
            # ADK BaseAgent name is readable.
            # We can try to set the name, but internal sub-agents might have refs? 
            # Usually safe to rename the root of a workflow.
            sub_agent.name = agent_config.name 
            
            if agent_config.description:
                sub_agent.description = agent_config.description
                
            return sub_agent
            
        except Exception as e:
            raise RuntimeError(f"Failed to load sub-workflow '{agent_config.path}': {e}")
    
    def _create_external_agent(self, agent_config: AgentConfig) -> ExternalAgent:
        """Create an external agent."""
        if not agent_config.url:
            raise ValueError(f"External agent '{agent_config.name}' requires 'url'")
            
        return ExternalAgent(
            name=agent_config.name,
            url=agent_config.url,
            method=agent_config.method or "POST",
            headers=agent_config.headers or {},
            output_key=agent_config.output_key,
            description=agent_config.description or "",
        )
    
    def _create_a2a_agent(self, agent_config: AgentConfig) -> A2AAgent:
        """Create an A2A agent."""
        if not agent_config.url:
            raise ValueError(f"A2A agent '{agent_config.name}' requires 'url'")
        if not agent_config.target_agent_id:
            raise ValueError(f"A2A agent '{agent_config.name}' requires 'target_agent_id'")
            
        return A2AAgent(
            name=agent_config.name,
            url=agent_config.url,
            target_agent_id=agent_config.target_agent_id,
            output_key=agent_config.output_key,
            description=agent_config.description or "",
        )

    def _create_interrupt_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """Create an interrupt agent."""
        from adk.core.interrupt_agent import InterruptAgent
        
        if not agent_config.output_key:
             raise ValueError(f"Interrupt agent '{agent_config.name}' requires 'output_key' to store human input.")

        # Resolve Tool (Tool capability)
        tool_func = None
        if agent_config.tool_name:
            tool_func = self.tools.get(agent_config.tool_name)

        # Resolve LLM Agent (Prompt capability)
        llm_agent = None
        if agent_config.instruction:
            # We create a temporary LlmAgent config
            from adk.config.schema import AgentConfig as LlmAgentConfig
            
            # The name for the inner agent
            inner_name = f"{agent_config.name}_prompt_generator"
            
            # Use the same model/etc
            llm_config = LlmAgentConfig(
                name=inner_name,
                type="llm",
                instruction=agent_config.instruction,
                instruction_variables=agent_config.instruction_variables,
                model=agent_config.model,
                # We don't save output_key for the prompt generator, it's captured directly
                output_key=None 
            )
            
            # Use standard factory logic to create it
            llm_agent = self._create_llm_agent(llm_config)

        return InterruptAgent(
            name=agent_config.name,
            interaction_mode=agent_config.interaction_mode or "text",
            message=agent_config.message,
            output_key=agent_config.output_key,
            tool_func=tool_func,
            tool_args=agent_config.arguments or {},
            llm_agent=llm_agent,
            description=agent_config.description or "",
        )

    def _create_fan_out_router_agent(self, agent_config: AgentConfig) -> BaseAgent:
        """Create a fan-out router agent."""
        from adk.core.fan_out_router_agent import FanOutRouterAgent

        # Resolve all targets
        route_agents = {}
        targets = set()
        
        if agent_config.routing_rules:
            for rule in agent_config.routing_rules:
                t = rule.get("target")
                if t:
                    targets.add(t)
                
        if agent_config.default_route:
            targets.add(agent_config.default_route)
            
        for t_name in targets:
             if t_name in self._created_agents:
                 route_agents[t_name] = self._created_agents[t_name]
             else:
                 cfg = self.config.get_agent_by_name(t_name)
                 if not cfg:
                     raise ValueError(f"FanOut target agent '{t_name}' not found")
                 route_agents[t_name] = self.create_agent(cfg)
                 
        default_agent = None
        if agent_config.default_route:
            default_agent = route_agents[agent_config.default_route]
            
        return FanOutRouterAgent(
            name=agent_config.name,
            routing_rules=agent_config.routing_rules or [],
            route_agents=route_agents,
            default_route_agent=default_agent,
            fan_in_strategy=agent_config.fan_in_strategy,
            output_key=agent_config.output_key,
            description=agent_config.description or ""
        )

    def _create_sub_agents(self, sub_agent_names: list[str]) -> list[BaseAgent]:
        """Create sub-agents from their names."""
        sub_agents = []
        for agent_name in sub_agent_names:
            agent_config = self.config.get_agent_by_name(agent_name)
            if agent_config is None:
                raise ValueError(f"Sub-agent not found: {agent_name}")
            sub_agents.append(self.create_agent(agent_config))
        return sub_agents
    
    def get_created_agents(self) -> dict[str, BaseAgent]:
        """Get all created agents."""
        return self._created_agents.copy()
