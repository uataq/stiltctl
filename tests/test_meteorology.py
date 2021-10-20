import tempfile
from datetime import datetime
from pathlib import Path

from stiltctl.meteorology import crop_meteorology, xtrct_grid, xtrct_time

METEOROLOGY_PATH = (
    Path(__file__).parent
    / "data"
    / "buckets"
    / "high-resolution-rapid-refresh"
    / "noaa_arl_formatted"
)


def test_xtrct_grid():
    meteorology_path = METEOROLOGY_PATH / "20190530_00-05_hrrr"

    with tempfile.NamedTemporaryFile() as file_obj:
        output_path = Path(file_obj.name)
        xtrct_grid(
            input_path=meteorology_path,
            output_path=output_path,
            xmin=-112.5,
            xmax=-111.5,
            ymin=40.5,
            ymax=41.0,
            n_levels=10,
        )

        assert output_path.exists()
        assert output_path.stat().st_size < meteorology_path.stat().st_size


def test_xtrct_time():
    meteorology_path = METEOROLOGY_PATH / "20190530_00-05_hrrr"

    with tempfile.NamedTemporaryFile() as file_obj:
        output_path = Path(file_obj.name)
        xtrct_time(
            input_path=meteorology_path,
            output_path=output_path,
            tmin=datetime(2015, 5, 30, 2),
            tmax=datetime(2015, 5, 30, 4),
        )

        assert output_path.exists()
        result_size = output_path.stat().st_size
        assert result_size > 0
        assert result_size < meteorology_path.stat().st_size


def test_crop_meteorology():
    meteorology_paths = (
        METEOROLOGY_PATH / "20190530_00-05_hrrr",
        METEOROLOGY_PATH / "20190530_06-11_hrrr",
    )

    with tempfile.NamedTemporaryFile() as file_obj:
        output_path = Path(file_obj.name)
        crop_meteorology(
            meteorology_paths,
            output_path,
            xmin=-112.5,
            xmax=-111.5,
            ymin=40.5,
            ymax=41.0,
            tmin=datetime(2015, 5, 30, 3),
            tmax=datetime(2015, 5, 30, 8),
            n_levels=10,
        )

        assert output_path.exists()
        assert output_path.stat().st_size == 292560
