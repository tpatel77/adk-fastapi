"""Workflow orchestrator for executing ADK workflows."""

import asyncio
from pathlib import Path
from typing import Any

from google.adk.agents import BaseAgent
from google.adk.agents.run_config import RunConfig
from google.adk.agents.run_config import StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from adk.core.workflow_builder import WorkflowBuilder
from adk.config.schema import WorkflowConfig

# # Import built-in tools to ensure they're registered
# import adk.tools.builtin  # noqa: F401
# import adk.callbacks.std_callbacks  # noqa: F401
# import adk.callbacks.parsing_callbacks  # noqa: F401

from test_callbacks import callbacks  # noqa: F401


class WorkflowOrchestrator:
    """
    High-level orchestrator for loading and executing ADK workflows.
    
    Usage:
        orchestrator = WorkflowOrchestrator()
        orchestrator.load_workflow("workflows/my_workflow.yaml")
        result = orchestrator.run("Process this input")
        print(result)
    """
    
    def __init__(self, app_name: str = "adk_workflow"):
        """
        Initialize the orchestrator.
        
        Args:
            app_name: Application name for session management
        """
        self.app_name = app_name
        self.builder = WorkflowBuilder()
        self.root_agent: BaseAgent | None = None
        self.config: WorkflowConfig | None = None
        self._session_service = InMemorySessionService()
        self._runner: Runner | None = None
    
    def load_workflow(self, yaml_path: str | Path) -> "WorkflowOrchestrator":
        """
        Load a workflow from a YAML configuration file.
        
        Args:
            yaml_path: Path to the YAML configuration file
        
        Returns:
            Self for method chaining
        """
        self.root_agent = self.builder.build_from_yaml(yaml_path)
        self.config = self.builder.get_config()
        
        # Initialize Session Service based on Config
        session_backend = "memory"
        conn_str = None
        redis_conn_str = None
        database_conn_str = None
        redis_ttl_seconds = None

        app_config = None
        try:
            from fastapi_common.config.app_config import get_application_config

            app_config = get_application_config()
        except Exception:
            app_config = None
        
        if self.config and self.config.context:
            session_backend = self.config.context.session_storage
            # Backward compatible default
            conn_str = self.config.context.connection_string
            redis_conn_str = getattr(self.config.context, "redis_connection_string", None)
            database_conn_str = getattr(self.config.context, "database_connection_string", None)
            redis_ttl_seconds = getattr(self.config.context, "redis_ttl_seconds", None)

        app_redis_url = None
        app_redis_password = None
        app_database_url = None
        if app_config is not None:
            try:
                app_redis_url = app_config.get("service.redis.url")
                app_redis_password = app_config.get("service.redis.password")
                app_database_url = app_config.get("service.database.url")
            except Exception:
                pass
            
        if session_backend in {"redis", "redis_with_database"}:
            import os

            effective_redis_url = redis_conn_str or conn_str or app_redis_url or os.environ.get("REDIS_URL")
            if effective_redis_url and app_redis_password and "://" in effective_redis_url and "@" not in effective_redis_url:
                # Allow providing password separately in application.yaml
                scheme, rest = effective_redis_url.split("://", 1)
                effective_redis_url = f"{scheme}://:{app_redis_password}@{rest}"
            if not effective_redis_url:
                raise ValueError("Redis URL required. Set REDIS_URL env var or connection_string in YAML.")

            effective_db_url = None
            if session_backend == "redis_with_database":
                effective_db_url = database_conn_str or app_database_url or os.environ.get("DATABASE_URL")
                if not effective_db_url:
                    raise ValueError(
                        "Database URL required for redis_with_database. Set DATABASE_URL env var or database_connection_string in YAML."
                    )
            from adk.services.redis_session import RedisSessionService
            ttl = redis_ttl_seconds if isinstance(redis_ttl_seconds, int) else 3600
            self._session_service = RedisSessionService(
                redis_url=effective_redis_url,
                ttl_seconds=ttl,
                app_name=self.app_name,
                database_url=effective_db_url,
            )
            
        elif session_backend in {"database", "adk_database"}:
            import os
            effective_db_url = database_conn_str or conn_str or app_database_url or os.environ.get("DATABASE_URL")
            if not effective_db_url:
                raise ValueError("Database URL required. Set DATABASE_URL env var or connection_string in YAML.")
            from google.adk.sessions.database_session_service import DatabaseSessionService
            self._session_service = DatabaseSessionService(db_url=effective_db_url)
            
        else:
            # Default to InMemory
            self._session_service = InMemorySessionService()
        
        # Create the runner
        self._runner = Runner(
            agent=self.root_agent,
            app_name=self.app_name,
            session_service=self._session_service,
        )
        
        return self
    
    async def run_async(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ) -> str:
        """
        Execute the workflow asynchronously with the given input.
        
        Args:
            user_input: The user's input to process
            user_id: User identifier for session management
            session_id: Optional session ID (creates new if not provided)
            initial_state: Optional dictionary of context variables to inject
        
        Returns:
            The final output from the workflow
        """
        if self._runner is None or self.config is None:
            raise ValueError("No workflow loaded. Call load_workflow() first.")
        
        # Create or get session
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
        
        session = await self._session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        
        if session is None:
            session = await self._session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            
        # Inject initial state into StartAgent for proper lifecycle handling
        if initial_state:
            start_agent = self.builder.get_start_agent()
            if start_agent:
                start_agent.initial_state = initial_state
        
        # Create user message
        user_message = types.Content(
            role="user",
            parts=[types.Part(text=user_input)],
        )
        
        # Run the workflow and collect responses
        final_response = ""
        try:
            async for event in self._runner.run_async(
                user_id=user_id,
                session_id=session_id,
                new_message=user_message,
            ):
                # Collect text from agent responses
                if hasattr(event, 'content') and event.content:
                    if hasattr(event.content, 'parts') and event.content.parts:
                        for part in event.content.parts:
                            if hasattr(part, 'text') and part.text:
                                final_response = part.text
        
        except Exception as e:
            # Check for Interrupt
            if e.__class__.__name__ == 'WorkflowInterruption':
                # It is an interrupt. Return a structured JSON or special string
                import json
                return json.dumps({
                    "status": "paused",
                    "agent": getattr(e, "agent_name", "unknown"),
                    "message": getattr(e, "message", ""),
                    "mode": getattr(e, "mode", "text"),
                    "resume_key": getattr(e, "resume_key", "")
                })
            raise e
        
        return final_response

    async def run_stream(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ):
        """
        Execute the workflow and yield events for streaming/tracing.
        
        Yields:
             ADK Events (start, output, end, etc.)
        """
        if self._runner is None:
             raise ValueError("No workflow loaded")
             
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
            
        session = await self._session_service.get_session(
            app_name=self.app_name,
            user_id=user_id,
            session_id=session_id,
        )
        if session is None:
            session = await self._session_service.create_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            
        # Inject initial state if provided
        if initial_state and self.builder.state_manager:
            for k, v in initial_state.items():
                self.builder.state_manager.set(
                    scope="workflow",
                    key=k, 
                    value=v, 
                    session_id=session_id
                )
            
                if session:
                    session.state[k] = v
                    # Persist for InMemory
                    if hasattr(self._session_service, "sessions") and session_id in self._session_service.sessions:
                        self._session_service.sessions[session_id].state[k] = v
            
        user_message = types.Content(
            role="user",
            parts=[types.Part(text=user_input)],
        )

        run_config = RunConfig(streaming_mode=StreamingMode.SSE)
        
        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=user_message,
            run_config=run_config,
        ):
            yield event

    def run(
        self,
        user_input: str,
        user_id: str = "default_user",
        session_id: str | None = None,
        initial_state: dict[str, Any] | None = None,
    ) -> str:
        """
        Execute the workflow synchronously with the given input.
        
        Args:
            user_input: The user's input to process
            user_id: User identifier for session management
            session_id: Optional session ID
            initial_state: Optional dictionary of context variables to inject
        
        Returns:
            The final output from the workflow
        """
        return asyncio.run(self.run_async(user_input, user_id, session_id, initial_state))
    
    def get_session_state(self, user_id: str = "default_user", session_id: str | None = None) -> dict[str, Any]:
        """
        Get the current session state.
        
        Args:
            user_id: User identifier
            session_id: Session identifier
        
        Returns:
            The session state dictionary
        """
        if self.config is None:
            return {}
        
        if session_id is None:
            import uuid
            session_id = str(uuid.uuid4())
        
        async def _get_state() -> dict[str, Any]:
            session = await self._session_service.get_session(
                app_name=self.app_name,
                user_id=user_id,
                session_id=session_id,
            )
            return dict(session.state) if session else {}
        
        return asyncio.run(_get_state())
    
    def get_root_agent(self) -> BaseAgent | None:
        """Get the root agent for ADK tools compatibility."""
        return self.root_agent
