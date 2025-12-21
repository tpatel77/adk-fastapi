"""
Redis Session Service for ADK.
Implements the BaseSessionService interface using Redis for storage with TTL support.
"""

import json
import logging
import time
from typing import Any, AsyncGenerator

from google.adk.sessions import BaseSessionService, Session, InMemorySessionService
from google.adk.sessions.database_session_service import DatabaseSessionService

logger = logging.getLogger(__name__)

class RedisSessionService(BaseSessionService):
    """
    Session Service backed by Redis with TTL support.
    Can optionally wrap a DatabaseSessionService for write-through persistence.
    """

    def __init__(
        self, 
        redis_url: str, 
        ttl_seconds: int = 3600, 
        app_name: str = "adk_app",
        database_url: str | None = None
    ):
        try:
            import redis
            from redis import Redis
        except ImportError:
            raise ImportError("redis package is required. Install with 'pip install redis'")

        self.client: Redis = redis.from_url(redis_url, decode_responses=True)
        self.ttl = ttl_seconds
        self.app_name = app_name
        self.db_service: DatabaseSessionService | None = None
        
        if database_url:
            self.db_service = DatabaseSessionService(db_url=database_url)
            logger.info("Enabled Write-Through to DatabaseSessionService")

    def _get_key(self, session_id: str) -> str:
        return f"{self.app_name}:session:{session_id}"

    async def get_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> Session | None:
        """Get session from Redis, fallback to DB if enabled."""
        key = self._get_key(session_id)
        data = self.client.get(key)
        
        if data:
            # Hit in Redis
            self.client.expire(key, self.ttl) # Reset TTL
            try:
                session_dict = json.loads(data)
                # Reconstruct Session object
                return Session(
                    id=session_id,
                    user_id=user_id,
                    app_name=app_name,
                    state=session_dict.get("state", {}),
                )
            except json.JSONDecodeError:
                logger.error(f"Corrupt session data for {session_id}")
                return None

        # Miss in Redis, check DB
        if self.db_service:
            session = await self.db_service.get_session(app_name, user_id, session_id)
            if session:
                # Populate Redis (Read Repair)
                self._save_to_redis(session)
                return session

        return None

    async def create_session(
        self,
        app_name: str,
        user_id: str,
        session_id: str,
    ) -> Session:
        """Create a new session in Redis and DB."""
        session = Session(
            id=session_id,
            user_id=user_id,
            app_name=app_name,
            state={},
        )
        
        self._save_to_redis(session)
        
        if self.db_service:
            await self.db_service.create_session(app_name, user_id, session_id)
            
        return session

    def _save_to_redis(self, session: Session):
        """Helper to save/update session in Redis with TTL."""
        key = self._get_key(session.id)
        data = {
            "id": session.id,
            "user_id": session.user_id,
            "app_name": session.app_name,
            "state": session.state
            # History is typically too large for simple Redis Key-String, 
            # usually stored in Redis List or skipped. 
            # For this impl we skip history in the 'session' wrapper unless needed.
        }
        self.client.setex(key, self.ttl, json.dumps(data))

    async def delete_session(self, session_id: str) -> None:
        """Delete from Redis and DB."""
        key = self._get_key(session_id)
        self.client.delete(key)
        
        if self.db_service:
            await self.db_service.delete_session(session_id)

    # Note: ADK Runner might call internal methods or access .sessions directly if it assumes InMemory
    # We must ensure we implement what Runner needs. 
    # Usually Runner uses get_session/create_session.
    
    # Implementing abstract methods required by BaseSessionService?
    # Inspecting BaseSessionService usually reveals:
    # get_session, create_session, delete_session, list_sessions
    
    async def list_sessions(self, app_name: str, user_id: str) -> list[Session]:
        # Expensive scan in Redis, delegating to DB if available
        if self.db_service:
            return await self.db_service.list_sessions(app_name, user_id)
        return []

    async def append_event(self, *args, **kwargs) -> None:
        """
        Append an event to the session and update state.
        Critically, this must handle state_delta application.
        Accepts 'session' kwarg if provided by runner for optimization.
        """
        # Resolve arguments robustly
        session_id = kwargs.get('session_id')
        event = kwargs.get('event')
        
        if not session_id and len(args) > 0:
            session_id = args[0]
        if not event and len(args) > 1:
            event = args[1]
            
        # Optimization: If session object is provided
        session = kwargs.get("session")
        
        if not session_id and session:
            session_id = session.id
            
        if not session_id:
            logger.error("append_event called without session_id")
            return
            
        # 1. Update State in Redis & Append to History
        key = self._get_key(session_id)
        history_key = f"{key}:history"
        
        # Serialize Event
        # Pydantic v2: model_dump_json(), v1:.json()
        try:
            if hasattr(event, "model_dump_json"):
                event_json = event.model_dump_json() # Pydantic v2
            elif hasattr(event, "json"):
                event_json = event.json() # Pydantic v1
            else:
                # Fallback purely for simple dicts or str
                event_json = json.dumps(event if isinstance(event, dict) else str(event))
            
            # Push to history list
            self.client.rpush(history_key, event_json)
            self.client.expire(history_key, self.ttl)
        except Exception as e:
            logger.error(f"Error serializing event for Redis history: {e}")

        # Optimization: If session object is provided, use its current state directly
        # This avoids read-modify-write and ensures we match in-memory state exactly
        session = kwargs.get("session")
        
        if session:
            # We have the latest session state
            data = {
                "id": session.id,
                "user_id": session.user_id,
                "app_name": session.app_name,
                "state": session.state
            }
            try:
                self.client.setex(key, self.ttl, json.dumps(data))
            except Exception as e:
                logger.error(f"Error saving session state to Redis: {e}")
        else:
            # Fallback: Read-Modify-Write using Deltas
            data_str = self.client.get(key)
            if data_str:
                try:
                    data = json.loads(data_str)
                    current_state = data.get("state", {})
                    
                    # Apply Deltas
                    if event.actions and event.actions.state_delta:
                        # Merge delta
                        current_state.update(event.actions.state_delta)
                        data["state"] = current_state
                        
                        # Write back to Redis
                        self.client.setex(key, self.ttl, json.dumps(data))
                        
                except Exception as e:
                    logger.error(f"Error updating redis state for {session_id}: {e}")
            else:
                 logger.warning(f"Session {session_id} not found in Redis during append_event")

        # 2. Write-Through to DB (Persist History + State)
        if self.db_service:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await self.db_service.append_event(session_id, event, **kwargs)
                    break # Success
                except Exception as e:
                    is_stale = "last_update_time" in str(e) or "stale session" in str(e) or "version conflict" in str(e).lower()
                    if is_stale and attempt < max_retries - 1:
                        logger.warning(f"Optimistic lock conflict for session {session_id} (attempt {attempt+1}/{max_retries}). Retrying...")
                        
                        # Refresh session metadata from DB
                        try:
                            fresh_session = await self.db_service.get_session(
                                app_name=session.app_name if session else self.app_name,
                                user_id=session.user_id if session else "unknown",
                                session_id=session_id
                            )
                            
                            # If we have a local session object, update its timestamps to match DB
                            # allowing the save to proceed
                            if session and fresh_session:
                                # Update timestamp/version fields dynamically
                                if hasattr(fresh_session, "last_update_time"):
                                    session.last_update_time = fresh_session.last_update_time
                                if hasattr(fresh_session, "version"):
                                    session.version = fresh_session.version
                                    
                                # Important: We must preserve the 'state' from our local session (which has the new changes)
                                # but we need valid timestamps from DB.
                                # The DB service likely checks session.last_update_time vs DB.
                                
                                # Continue to next retry loop which calls append_event again
                                continue
                        except Exception as refresh_error:
                            logger.error(f"Failed to refresh session during retry: {refresh_error}")
                            
                    # If not stale error or retries exhausted, re-raise
                    logger.error(f"Failed to append event to DB for session {session_id}: {e}")
                    raise e
