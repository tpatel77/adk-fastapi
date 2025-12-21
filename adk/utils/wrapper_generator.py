
import os
import shutil
import sys
from pathlib import Path

def generate_wrappers(project_root: Path | None = None):
    """
    Generate ADK agent wrappers for YAML workflows.
    
    Args:
        project_root: Optional path to project root. Defaults to CWD.
    """
    if project_root is None:
        project_root = Path.cwd()
        
    workflows_dir = project_root / "workflows"
    adk_agents_dir = project_root / "src" / "adk_agents"

    if not workflows_dir.exists():
        print(f"Warning: Workflows directory not found at {workflows_dir}")
        return

    # Clean target dir
    if adk_agents_dir.exists():
        shutil.rmtree(adk_agents_dir)
    adk_agents_dir.mkdir(parents=True)

    # Agent template
    template = """
import sys
import os
from pathlib import Path

# Add project root to path (3 levels up from src/adk_agents/name/agent.py)
# src/adk_agents/name -> src -> root
# This allows importing adk.orchestrator
sys.path.append(str(Path(__file__).parents[3]))

from adk.orchestrator import WorkflowOrchestrator

# Configured YAML path
YAML_PATH = "{yaml_path}"

orchestrator = WorkflowOrchestrator()
orchestrator.load_workflow(YAML_PATH)
# ADK loader expects 'root_agent' variable
root_agent = orchestrator.root_agent
"""

    # Scan YAMLs
    print(f"Scanning {workflows_dir}...")
    count = 0
    for yaml_file in workflows_dir.glob("*.yaml"):
        agent_name = yaml_file.stem
        # ADK agents usually expect snake_case folder names
        agent_dir = adk_agents_dir / agent_name
        agent_dir.mkdir()

        # Create __init__.py
        (agent_dir / "__init__.py").touch()

        # Create agent.py
        with open(agent_dir / "agent.py", "w") as f:
             # We use absolute path for YAML to be safe in generated code
             f.write(template.format(yaml_path=str(yaml_file.absolute())))
        
        print(f"Generated wrapper for {agent_name}")
        count += 1
    
    print(f"Done. Generated {count} agent wrappers in {adk_agents_dir}")

if __name__ == "__main__":
    generate_wrappers()
