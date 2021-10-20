from datetime import datetime

from stiltctl.dtos import DomainConfig
from stiltctl.meteorology import MeteorologyModel
from stiltctl.simulations import SimulationConfig
from stiltctl.spatial import Grid

DOMAIN_CONFIG = DomainConfig(
    receptor_grid=Grid(
        xmin=-112.1, xmax=-111.7, xres=0.01, ymin=40.4, ymax=40.9, yres=0.01
    ),
    simulation_config=SimulationConfig(
        n_hours=-2,
        numpar=10,
        xmn=-112.5,
        xmx=-111.5,
        xres=0.002,
        ymn=40.1,
        ymx=41.2,
        yres=0.002,
    ),
    meteorology_model=MeteorologyModel.HRRR,
    time=datetime(2019, 5, 30, 7, 1, 2, 3),
)


def test_domain_config_is_hashable():
    assert DOMAIN_CONFIG.scene_id == "cc1438bcc4e93db1daa9681015b10340"
