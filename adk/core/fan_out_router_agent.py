import logging
import asyncio
import re
from typing import Any, AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from pydantic import Field

logger = logging.getLogger(__name__)

class FanOutRouterAgent(BaseAgent):
    """
    Fan-out router that evaluates multiple conditions and executes matching agents in parallel.
    Aggregates results based on fan_in_strategy.
    """
    
    routing_rules: list[dict[str, str]] = Field(
        default_factory=list, 
        description="List of {condition, target} rules"
    )
    
    # We store the resolved agent instances here. 
    # Use a dict mapping agent_name -> Agent instance.
    route_agents: dict[str, BaseAgent] = Field(
        default_factory=dict, 
        description="Map of agent names to instances for all possible routes"
    )
    
    default_route_agent: BaseAgent | None = Field(None, description="Agent to run if no rules match")
    
    fan_in_strategy: str | None = Field(None, description="Aggregation strategy: list, dict")
    output_key: str | None = Field(None, description="State key for aggregated output")
    
    model_config = {"arbitrary_types_allowed": True}

    def _evaluate_condition(self, condition: str, state: dict[str, Any]) -> bool:
        """Evaluate a python condition against state."""
        try:
            # allow {var} syntax by stripping brackets (simple substitution support)
            # or just rely on standard python eval with state as locals
            clean_condition = re.sub(r'\{(\w+)\}', r'\1', condition)
            result = eval(clean_condition, {}, state)
            return bool(result)
        except Exception as e:
            logger.error(f"Error evaluating condition '{condition}': {e}")
            return False

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        if not ctx.session:
            logger.warning("No session in context")
            return

        state = dict(ctx.session.state)
        selected_agents: list[BaseAgent] = []
        
        # 1. Evaluate rules
        matched_any = False
        for rule in self.routing_rules:
            cond = rule.get("condition")
            target_name = rule.get("target")
            
            if cond and target_name:
                if self._evaluate_condition(cond, state):
                    matched_any = True
                    agent = self.route_agents.get(target_name)
                    if agent:
                        selected_agents.append(agent)
                    else:
                        logger.error(f"Target agent '{target_name}' not found in route_agents")
        
        # 2. Check default
        if not matched_any and self.default_route_agent:
            logger.info(f"No rules matched. selecting default route: {self.default_route_agent.name}")
            selected_agents.append(self.default_route_agent)
            
        if not selected_agents:
            logger.info("No agents selected for fan-out.")
            return

        logger.info(f"Fan-out router '{self.name}' selected {len(selected_agents)} agents: {[a.name for a in selected_agents]}")

        # 3. Execute in Parallel (Fan Out)
        # Using a queue to collect events from all sub-agents
        queue: asyncio.Queue[Event | None] = asyncio.Queue()

        async def _worker(agent: BaseAgent):
            try:
                async for event in agent._run_async_impl(ctx):
                    await queue.put(event)
            except Exception as e:
                logger.error(f"Error in fan-out agent {agent.name}: {e}")
            
        tasks = [asyncio.create_task(_worker(a)) for a in selected_agents]
        
        async def _monitor():
            await asyncio.gather(*tasks, return_exceptions=True)
            await queue.put(None) # Sentinel
            
        asyncio.create_task(_monitor())
        
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event
            
        # 4. Fan In (Aggregation)
        if self.fan_in_strategy and self.output_key:
            logger.info(f"Performing fan-in ({self.fan_in_strategy}) for {self.name}")
            # Refresh state as agents ran
            current_state = ctx.session.state
            
            gathered_data = None
            
            if self.fan_in_strategy == "list":
                gathered_data = []
                for agent in selected_agents:
                    out_key = getattr(agent, "output_key", None)
                    if out_key and out_key in current_state:
                         gathered_data.append(current_state[out_key])
                    else:
                         gathered_data.append(None)
                         
            elif self.fan_in_strategy == "dict":
                gathered_data = {}
                for agent in selected_agents:
                    out_key = getattr(agent, "output_key", None)
                    if out_key and out_key in current_state:
                        gathered_data[agent.name] = current_state[out_key]
                    else:
                        gathered_data[agent.name] = None
                        
            if gathered_data is not None:
                ctx.session.state[self.output_key] = gathered_data
                logger.info(f"Fan-in complete. Saved to '{self.output_key}'")
