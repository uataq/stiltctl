"""
This module contains persistence models and service classes.
"""

from dataclasses import dataclass
from typing import Optional, Sequence, Type, TypeVar, Union

from cloudstorage import Container  # type: ignore
from loguru import logger
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.session import Session  # type: ignore
from sqlalchemy.sql.expression import asc, func

from stiltctl.events import Event
from stiltctl.exceptions import NotFound
from stiltctl.simulations import Simulation

T = TypeVar("T")


@dataclass
class EventRecord:
    event_name: str
    event_data: Event
    id: Optional[int] = None

    @classmethod
    def from_event(cls, event: Event) -> "EventRecord":
        return cls(event_name=cls.get_event_name(event), event_data=event)

    @staticmethod
    def get_event_name(event: Union[Event, Type[Event], Type[T]]) -> str:
        module = event.__module__
        if isinstance(event, Event):
            event_name = type(event).__qualname__
        else:
            event_name = event.__qualname__
        return f"{module}.{event_name}"


class EventQueue:
    def __init__(self, session: Session):
        """Transactional queue backed by postgres."""
        self.session = session

    def add(self, event: Event):
        """Insert event into queue."""
        logger.debug(f"Publishing: {repr(event)}")
        self.session.add(EventRecord.from_event(event))

    def add_many(self, events: Sequence[Event]):
        """Insert events into queue."""
        self.session.add_all([EventRecord.from_event(event) for event in events])

    def dequeue(self, event_type: Type[T]) -> T:
        result = self.session.execute(
            select(EventRecord)
            .filter_by(event_name=EventRecord.get_event_name(event_type))
            .order_by(asc(EventRecord.id))
            .limit(1)
            .with_for_update(skip_locked=True)
        ).one_or_none()
        if not result:
            raise NotFound(event_type)

        event_record = result[0]
        self.session.execute(delete(EventRecord).filter_by(id=event_record.id))

        event = event_record.event_data
        logger.debug(f"Received: {repr(event)}")
        return event

    def get_event_count(self, event_type: Type[T]) -> int:
        result = self.session.execute(
            select([func.count()])
            .select_from(EventRecord)
            .filter_by(event_name=EventRecord.get_event_name(event_type))
        ).one()
        return result[0]


@dataclass
class SceneRecord:
    scene_id: str
    successful_simulations: int
    total_simulations: int
    id: Optional[int] = None


class SceneRepository:
    def __init__(self, session: Session):
        """Transactional queue backed by postgres."""
        self.session = session

    def add(self, scene: SceneRecord):
        """Persist simulation to storage."""
        self.session.add(scene)

    def get(self, scene_id: str, lock_for_update: bool = True):
        query = select(SceneRecord).filter_by(scene_id=scene_id)
        if lock_for_update:
            query = query.with_for_update()
        result = self.session.execute(query).one()
        return result[0]


class SimulationRepository:
    def __init__(self, bucket: Container):
        self.bucket = bucket

    def add(self, simulation: Simulation):
        """Persist simulation to storage."""
        if simulation.footprint_image:
            with open("/tmp/footprint.png", "wb") as f:
                f.write(simulation.footprint_image)
            self.bucket.upload_blob(
                "/tmp/footprint.png",
                blob_name=f"by-simulation-id/{simulation.id}/footprint.png",
                meta_data={
                    "id": f"{simulation.receptor.id}",
                    "xmin": f"{simulation.config.xmn}",
                    "xmax": f"{simulation.config.xmx}",
                    "ymin": f"{simulation.config.ymn}",
                    "ymax": f"{simulation.config.ymx}",
                },
                acl="public-read",
            )

        self.bucket.upload_blob(
            simulation.footprint_path,
            blob_name=f"by-simulation-id/{simulation.id}/footprint.nc",
        )
        self.bucket.upload_blob(
            simulation.trajectory_path,
            blob_name=f"by-simulation-id/{simulation.id}/trajectories.rds",
        )
