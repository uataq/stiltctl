import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from typer.testing import CliRunner

from stiltctl.cli import app
from stiltctl.dtos import DomainConfig
from stiltctl.meteorology import MeteorologyModel
from stiltctl.simulations import SimulationConfig
from stiltctl.spatial import Grid
from stiltctl.unit_of_work import UnitOfWork

runner = CliRunner()

DOMAIN_CONFIG = DomainConfig(
    receptor_grid=Grid(
        xmin=-112.11, xmax=-112.1, xres=0.01, ymin=40.4, ymax=40.41, yres=0.01
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


def test_e2e(uow: UnitOfWork):
    domain_config_yaml = DOMAIN_CONFIG.to_yaml()
    tempdir = tempfile.TemporaryDirectory()
    dirname = tempdir.name
    with open(Path(dirname) / "scene_a.yaml", "w") as f:
        f.write(domain_config_yaml)
    with uow:
        count = uow.session.execute(text("select count(*) from events")).scalar_one()
        assert count == 0

    result = runner.invoke(app, ["generate-scenes", dirname])
    assert result.exit_code == 0, result.stdout
    with uow:
        count = uow.session.execute(text("select count(*) from events")).scalar_one()
        assert count == 1

    result = runner.invoke(app, ["minimize-meteorology"])
    assert result.exit_code == 0, result.stdout
    assert Path("/tmp/meteorology.arl").exists()
    assert Path("/tmp/meteorology.arl").stat().st_size == 1415560
    with uow:
        count = uow.session.execute(text("select count(*) from events")).scalar_one()
        assert count == 1

    result = runner.invoke(app, ["generate-simulations"])
    assert result.exit_code == 0, result.stdout

    result = runner.invoke(app, ["execute-simulations", "--exit-on-empty"])
    assert result.exit_code == 0, result.stdout
