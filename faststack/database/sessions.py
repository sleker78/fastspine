from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from ..ctx.ctx_pool import ctxpool
from ..util.debug_util import DebugUtil

SESSION_CTX_NAME = "session_connection_pool"

session_connection_pool = ctxpool.new(SESSION_CTX_NAME, default=None)


class SessionConnectionPool:
    """Session connection pool.

    Pooled sessions are keyed by an owner key (e.g. a `RepositoryManager` subclass), not by the
    session's own class, since several owners may share the same underlying `Session`/`AsyncSession` type.
    """

    def __init__(self):
        self.pool: dict[str, Session | AsyncSession] = {}

    def _key_name(self, key: type[Any]) -> str:
        return key.__name__

    def _refresh(self):
        """Refresh the context variable with the current session connection pool."""
        ctxpool.set("session_connection_pool", self)

    def _clear_ctx(self):
        ctxpool.clear_one("session_connection_pool")

    def get(self, key: type[Any]) -> Session | AsyncSession | None:
        """Get the session from the pool."""
        return self.pool.get(self._key_name(key))

    def add(self, key: type[Any], value: Session | AsyncSession):
        """Add the session to the pool."""
        key_name = self._key_name(key)
        if self.pool.get(key_name) is not None:
            raise ValueError(f"Session for {key_name} already exists in the pool.")
        self.pool[key_name] = value
        self._refresh()

    def delete(self, key: type[Any]):
        """Delete the session from the pool."""
        key_name = self._key_name(key)
        if key_name not in self.pool:
            return  # Session not in pool, nothing to delete
        session = self.pool[key_name]
        session.close()
        del self.pool[key_name]
        self._refresh()

    async def adelete(self, key: type[Any]):
        """Async delete the session from the pool."""
        key_name = self._key_name(key)
        if key_name not in self.pool:
            return  # Session not in pool, nothing to delete
        session = self.pool[key_name]
        if isinstance(session, AsyncSession):
            await session.close()
        else:
            session.close()
        del self.pool[key_name]
        self._refresh()

    def clear(self):
        """Clear the session pool."""
        for session in self.pool.values():
            if isinstance(session, (Session, AsyncSession)):
                DebugUtil.debug(f"Closing session {session} with id {id(session)}")
                # Close the session
                session.close()
        self.pool.clear()
        self._refresh()

    async def aclear(self):
        """Async clear the session pool."""
        sessions = list(self.pool.values())
        for session in sessions:
            if isinstance(session, AsyncSession):
                DebugUtil.debug(f"Closing async session {session} with id {id(session)}")
                await session.close()
            elif isinstance(session, Session):
                DebugUtil.debug(f"Closing session {session} with id {id(session)}")
                session.close()
        self.pool.clear()
        self._refresh()

    @staticmethod
    def run() -> "SessionConnectionPool":
        """Start the session connection pool."""
        session_connection_pool = ctxpool.get(SESSION_CTX_NAME, default=None)
        if session_connection_pool is None:
            DebugUtil.debug("Creating a new session connection pool.")
            session_connection_pool = ctxpool.set(SESSION_CTX_NAME, SessionConnectionPool())
        if not isinstance(session_connection_pool, SessionConnectionPool):
            raise ValueError(
                "Session connection pool is not instance of SessionConnectionPool. Received type: "
                f"{type(session_connection_pool)}"
            )

        return session_connection_pool

    @staticmethod
    def stop():
        """Stop the session connection pool."""
        session_connection_pool = ctxpool.get(SESSION_CTX_NAME, default=None)
        if (session_connection_pool is not None) and isinstance(session_connection_pool, SessionConnectionPool):
            session_connection_pool.clear()

        ctxpool.clear_one(SESSION_CTX_NAME)
        DebugUtil.debug("Session connection pool stopped.")

    @staticmethod
    async def astop():
        """Async stop the session connection pool."""
        session_connection_pool = ctxpool.get(SESSION_CTX_NAME, default=None)
        if (session_connection_pool is not None) and isinstance(session_connection_pool, SessionConnectionPool):
            await session_connection_pool.aclear()

        ctxpool.clear_one(SESSION_CTX_NAME)
        DebugUtil.debug("Session connection pool stopped.")
