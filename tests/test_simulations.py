import tempfile
from datetime import datetime
from pathlib import Path

from stiltctl.exceptions import SimulationResultException
from stiltctl.meteorology import crop_meteorology
from stiltctl.simulations import (
    ColumnReceptor,
    Simulation,
    SimulationConfig,
    SurfaceReceptor,
)
from tests.test_meteorology import METEOROLOGY_PATH


def test_surface_receptor_kwargs():
    receptor = SurfaceReceptor(
        time=datetime(2019, 5, 30, 7),
        longitude=-111.847672,
        latitude=40.766189,
        height=35,
    )
    stilt_kwargs = receptor.to_stilt_kwargs()
    expected = {
        "r_run_time": "2019-05-30T07:00:00",
        "r_long": -111.847672,
        "r_lati": 40.766189,
        "r_zagl": 35.0,
    }
    assert stilt_kwargs == expected


def test_column_receptor_kwargs():
    receptor = ColumnReceptor(
        time=datetime(2019, 5, 30, 7),
        longitude=(-111.8, -111.85),
        latitude=(40.7, 40.75),
        height=(0, 2000),
    )
    stilt_kwargs = receptor.to_stilt_kwargs()
    expected = {
        "r_run_time": "2019-05-30T07:00:00",
        "r_long": "-111.8,-111.85",
        "r_lati": "40.7,40.75",
        "r_zagl": "0,2000",
    }
    assert stilt_kwargs == expected


def test_surface_simulation():
    receptor = SurfaceReceptor(
        time=datetime(2019, 5, 30, 4),
        longitude=-111.847672,
        latitude=40.766189,
        height=35,
    )
    simulation_config = SimulationConfig(
        n_hours=-2,
        numpar=10,
        xmn=-112.0,
        xmx=-111.5,
        xres=0.002,
        ymn=40.5,
        ymx=41.0,
        yres=0.002,
        time_integrate=True,
    )

    simulation = Simulation(
        receptor=receptor,
        config=simulation_config,
        meteorology_path=METEOROLOGY_PATH / "20190530_00-05_hrrr",
    )
    simulation.execute()
    assert simulation.trajectory_path.exists()
    assert simulation.footprint_path.exists()
    simulation.cleanup()
    assert not simulation.footprint_path.exists()


def test_surface_simulation_missing_meteorology():
    receptor = SurfaceReceptor(
        time=datetime(2019, 5, 30, 4),
        longitude=-111.847672,
        latitude=40.766189,
        height=35,
    )
    simulation_config = SimulationConfig(
        n_hours=-2,
        numpar=10,
        xmn=-112.0,
        xmx=-111.5,
        xres=0.002,
        ymn=40.5,
        ymx=41.0,
        yres=0.002,
        time_integrate=True,
    )
    # Using meteorological data that doesn't contain the simulation time window.
    simulation = Simulation(
        receptor=receptor,
        config=simulation_config,
        meteorology_path=METEOROLOGY_PATH / "20190530_06-11_hrrr",
    )
    try:
        simulation.execute()
    except SimulationResultException:
        pass
    simulation.cleanup()


def test_surface_simulation_with_meteorology_aggregate():
    scene_id = "test-fake-scene-uuid"
    receptor = SurfaceReceptor(
        time=datetime(2019, 5, 30, 7),
        longitude=-111.847672,
        latitude=40.766189,
        height=35,
    )
    simulation_config = SimulationConfig(
        n_hours=-2,
        numpar=10,
        xmn=-112.0,
        xmx=-111.5,
        xres=0.002,
        ymn=40.5,
        ymx=41.0,
        yres=0.002,
    )

    tempdir = tempfile.TemporaryDirectory()
    meteorology_path = Path(tempdir.name) / scene_id
    crop_meteorology(
        input_paths=(
            METEOROLOGY_PATH / "20190530_00-05_hrrr",
            METEOROLOGY_PATH / "20190530_06-11_hrrr",
        ),
        output_path=meteorology_path,
        xmin=-112.5,
        xmax=-111.5,
        ymin=40.5,
        ymax=41.0,
        tmin=datetime(2015, 5, 30, 3),
        tmax=datetime(2015, 5, 30, 8),
        n_levels=10,
    )

    simulation = Simulation(
        receptor=receptor,
        config=simulation_config,
        meteorology_path=meteorology_path,
    )
    simulation.execute()

    assert simulation.trajectory_path.exists()
    assert simulation.footprint_path.exists()
    simulation.cleanup()
    assert not simulation.footprint_path.exists()


def test_column_simulation():
    receptor = ColumnReceptor(
        time=datetime(2019, 5, 30, 4),
        longitude=(-111.8, -111.85),
        latitude=(40.7, 40.75),
        height=(0, 2000),
    )
    simulation_config = SimulationConfig(
        n_hours=-2,
        numpar=10,
        xmn=-112.0,
        xmx=-111.5,
        xres=0.002,
        ymn=40.5,
        ymx=41.0,
        yres=0.002,
        time_integrate=True,
    )

    simulation = Simulation(
        receptor=receptor,
        config=simulation_config,
        meteorology_path=METEOROLOGY_PATH / "20190530_00-05_hrrr",
    )
    simulation.execute()

    assert simulation.trajectory_path.exists()
    assert simulation.footprint_path.exists()
    simulation.cleanup()
    assert not simulation.footprint_path.exists()
