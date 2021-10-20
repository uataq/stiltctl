"""
This module uses sqlalchemy to implement persistence models.
"""
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    Integer,
    PickleType,
    Table,
    Text,
    create_engine,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import make_url
from sqlalchemy.exc import OperationalError
from sqlalchemy.future.engine import Engine
from sqlalchemy.orm import Session, registry
from sqlalchemy.pool import NullPool
from sqlalchemy.types import TypeDecorator

from stiltctl.repositories import EventRecord, SceneRecord
from stiltctl.simulations import SimulationConfig

mapper_registry = registry()
metadata = mapper_registry.metadata


class SimulationConfigSerializer(TypeDecorator):
    """Map SimulationConfig between persistence and domain models.
    Uses postgres JSONB type for storing simulation parameters and reconstructs the
    SimulationConfig instance on load.
    """

    impl = JSONB
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return value.dict(exclude_defaults=True)

    def process_result_value(self, value, dialect):
        return SimulationConfig(**value)


event_table = Table(
    "events",
    metadata,
    Column("id", BigInteger, primary_key=True),
    Column(
        "created_at",
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
    Column("event_name", Text, nullable=False, index=True),
    Column("event_data", PickleType),
)

scene_table = Table(
    "scenes",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("scene_id", Text, index=True, unique=True),
    Column("created_at", DateTime, nullable=False, default=datetime.utcnow),
    Column(
        "updated_at",
        DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    ),
    Column("successful_simulations", Integer, nullable=False),
    Column("total_simulations", Integer, nullable=False),
)


def engine_factory(database_url: str) -> Engine:
    """Construct database connection pool."""
    url = make_url(database_url)
    engine_kwargs: dict[str, Any] = {}
    if url.host == "localhost":
        engine_kwargs = {
            **engine_kwargs,
            "connect_args": {"connect_timeout": 1},
            "echo": True,
        }

    return create_engine(
        database_url,
        future=True,
        poolclass=NullPool,
        executemany_mode="values",
        **engine_kwargs,
    )


def session_factory(engine: Engine) -> Session:
    """Construct session used for sqlalchemy transactions."""
    return Session(bind=engine, future=True)


def create_schema(engine: Engine):
    """Create missing tables from sqlalchemy schema.
    This will not resolve schema differences for existing databases. To perform
    formal migrations, use migra to generate a schema diff between the test and
    production databases. https://databaseci.com/docs/migra
    """
    metadata.create_all(bind=engine)


def drop_schema(engine: Engine, force: bool = True):
    """Remove all tracked tables from database."""
    if not force:
        if "localhost" not in engine.url:
            raise ValueError(
                f"Potentially destructive operation dropping all tables at {engine.url}"
                "Provide the `force=True` argument if you're sure you want to do this."
            )
    logger.info("Dropping all database tables.")
    metadata.drop_all(bind=engine)


def reset_schema(engine: Engine, force: bool = True):
    """Drop and create database schema."""
    drop_schema(engine, force)
    create_schema(engine)


def healthcheck(engine: Engine) -> bool:
    """Return True if database is accessible, False if not."""
    try:
        with engine.connect() as connection:
            result = connection.execute(select(1))
            assert result.first() == (1,)
        return True
    except (AssertionError, OperationalError) as e:
        return False


def configure_mappers():
    """Starts ORM mapping between domain and persistence models.
    If configure_mappers() is called during setup, domain models can be passed to the
    sqlalchemy session to add, delete, or update their
    """

    def map_model_to_table(model: type, table: Table):
        try:
            mapper_registry.map_imperatively(model, table)
        except AssertionError:
            pass

    map_model_to_table(EventRecord, event_table)
    map_model_to_table(SceneRecord, scene_table)
