import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import yaml
from pydantic import Field
from pydantic.main import BaseModel

from stiltctl.meteorology import MeteorologyModel
from stiltctl.simulations import AbstractReceptor, SimulationConfig, SurfaceReceptor
from stiltctl.spatial import Grid, GridTimeExtent
from stiltctl.utils import floor_time_to_hour


class SimulationManifest(BaseModel):
    """Fully qualified simulation configuration for execution."""

    config: SimulationConfig
    receptor: AbstractReceptor
    scene_id: str


class DomainConfig(BaseModel):
    """Configures an area of gridded simulations."""

    receptor_grid: Grid
    simulation_config: SimulationConfig
    meteorology_model: MeteorologyModel
    time: datetime = Field(default_factory=floor_time_to_hour)

    @property
    def scene_id(self) -> str:
        return hashlib.md5(repr(self).encode("utf-8")).hexdigest()

    def get_simulation_manifests(self) -> List[SimulationManifest]:
        """Construct SimulationManifests from the given configuration."""
        manifests = []
        points = self.receptor_grid.to_points()

        for point in points:
            receptor = SurfaceReceptor(
                time=self.time, longitude=point.x, latitude=point.y
            )
            manifests.append(
                SimulationManifest(
                    config=self.simulation_config,
                    receptor=receptor,
                    scene_id=self.scene_id,
                )
            )

        return manifests

    def get_meteorology_extent(self) -> GridTimeExtent:
        """Find the space/time extent containing all simulations."""
        n_hours = timedelta(hours=self.simulation_config.n_hours)
        time_matrix = (
            self.time,
            self.time + n_hours,
            self.time,
            self.time + n_hours,
        )
        tmin = min(time_matrix)
        tmax = max(time_matrix)

        spatial_extent = self.simulation_config.footprint_extent
        footprint_extent = GridTimeExtent(tmin=tmin, tmax=tmax, **spatial_extent.dict())
        meteorology_extent = footprint_extent.expand(
            dx=0.25, dy=0.25, dt=timedelta(hours=1)
        )
        meteorology_extent.tmin = floor_time_to_hour(meteorology_extent.tmin)
        meteorology_extent.tmax = floor_time_to_hour(
            meteorology_extent.tmax + timedelta(hours=1)
        )
        return meteorology_extent

    @classmethod
    def from_yaml(cls, path: Path):
        """Load config from a given yaml file."""
        with open(path) as f:
            return cls(**yaml.safe_load(f))

    def to_yaml(self) -> str:
        """Exports domain config to a yaml string."""
        return yaml.dump(json.loads(self.json(exclude_defaults=True)))
