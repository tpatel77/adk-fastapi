"""
CLI entry point for the ADK Workflow Framework.
"""

import argparse
import sys
import subprocess
from pathlib import Path

from adk.orchestrator import WorkflowOrchestrator
from adk.utils.wrapper_generator import generate_wrappers

def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="ADK Workflow Framework - Execute YAML-configured workflows",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Run a workflow with input
    python main.py --workflow workflows/example_sequential.yaml --input "Write a fibonacci function"
    
    # Interactive mode
    python main.py --workflow workflows/example_sequential.yaml
    
    # Show workflow info
    python main.py --workflow workflows/example_sequential.yaml --info
    
    # Launch Native ADK UI
    python main.py --ui
        """,
    )
    
    parser.add_argument(
        "--workflow", "-w",
        type=str,
        required=False,  # Optional if --ui is used
        help="Path to the workflow YAML configuration file",
    )
    
    parser.add_argument(
        "--input", "-i",
        type=str,
        help="Input to process through the workflow",
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Display workflow information and exit",
    )
    
    parser.add_argument("--ui", action="store_true", help="Launch the Native ADK Web UI")
    
    parser.add_argument(
        "--user-id",
        type=str,
        default="default_user",
        help="User ID for session management (default: default_user)",
    )
    
    args = parser.parse_args()

    # handle UI launch
    if args.ui:
        print("Generating ADK wrappers...")
        generate_wrappers()
        
        print("Launching ADK Web UI...")
        adk_path = Path(sys.executable).parent / "adk"
        if not adk_path.exists():
             adk_cmd = "adk"
        else:
             adk_cmd = str(adk_path)
             
        # Run adk web pointing to src/adk_agents
        # We need absolute path to src/adk_agents to be safe
        agents_dir = Path.cwd() / "src" / "adk_agents"
        subprocess.run([adk_cmd, "web", str(agents_dir), "--port", "8080"])
        return 0

    if not args.workflow:
        parser.error("--workflow is required unless --ui is specified")
    
    # Validate workflow path
    workflow_path = Path(args.workflow)
    if not workflow_path.exists():
        print(f"Error: Workflow file not found: {workflow_path}", file=sys.stderr)
        return 1
    
    try:
        # Load the workflow
        orchestrator = WorkflowOrchestrator()
        orchestrator.load_workflow(workflow_path)
        
        config = orchestrator.builder.get_config()
        if not config:
            raise ValueError("Failed to load config")

        # Info mode
        if args.info:
            print(f"\n{'='*60}")
            print(f"Workflow: {config.name}")
            print(f"Description: {config.description or 'No description'}")
            print(f"Type: {config.workflow.type}")
            print(f"Default Model: {config.defaults.model}")
            print(f"\nAgents ({len(config.agents)}):")
            for agent in config.agents:
                print(f"  - {agent.name} ({agent.type})")
            print(f"\nWorkflow Steps: {' → '.join(config.workflow.agents)}")
            print(f"{'='*60}\n")
            return 0
        
        # Get input
        user_input = args.input
        if not user_input:
            print(f"Workflow: {config.name}")
            print("Enter your input (press Enter twice to submit):")
            lines = []
            while True:
                line = input()
                if line == "":
                    break
                lines.append(line)
            user_input = "\n".join(lines)
        
        if not user_input.strip():
            print("Error: No input provided", file=sys.stderr)
            return 1
        
        print(f"\n{'='*60}")
        print(f"Running workflow: {config.name}")
        print(f"{'='*60}\n")
        
        # Run the workflow
        result = orchestrator.run(user_input, user_id=args.user_id)
        
        print(f"\n{'='*60}")
        print("Result:")
        print(f"{'='*60}")
        print(result)
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main())
