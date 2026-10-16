from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import Session

DBSessions = Session | AsyncSession
DBEngines = Engine | AsyncEngine
