from abc import ABC

from pydantic import BaseModel

from stiltctl.dtos import DomainConfig, SimulationManifest


class Event(BaseModel, ABC):
    """Abstract base event."""

    class Config:
        frozen = True


class SceneCreated(Event):
    domain_config: DomainConfig


class MeteorologyMinimized(Event):
    domain_config: DomainConfig


class SimulationCreated(Event):
    manifest: SimulationManifest
