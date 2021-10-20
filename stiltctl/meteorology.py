"""
Meteorological data management utilities.

Objects of type MeteorologySource have a reference to a root location in object
storage (artifact_bucket, artifact_prefix) and methods to construct the
filenames for a given datetime using a predefined filename_strptime_format.

The crop_meteorology service wraps the xtrct_grid and xtrct_time HYSPLIT
utilities packaged with STILT. These are useful for manipulating meteorological
data stored in the binary .arl format, which is unique to the HYSPLIT and STILT
models.

For an overview of the .arl format, see:
    https://www.ready.noaa.gov/HYSPLIT_data2arl.php

For technical documentation about the .arl format , see:
    https://www.ready.noaa.gov/hysplitusersguide/S141.htm
"""
import subprocess
import tempfile
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Iterable, List

from loguru import logger

from stiltctl.config import config_from_env
from stiltctl.exceptions import XtrctGridException, XtrctTimeException
from stiltctl.spatial import GridExtent

XTRCT_GRID = config_from_env.STILT_PATH / "exe" / "xtrct_grid"
XTRCT_TIME = config_from_env.STILT_PATH / "exe" / "xtrct_time"


class AbstractMeteorologySource(ABC):
    """Abstract base model for available MeteorologySources.

    Subclasses should override self.get_filename_by_time() with source specific
    methods to resolve meteorological filenames.
    """

    artifact_bucket: str
    artifact_prefix: str
    extent: GridExtent
    hours_per_file: int
    filename_strptime_format: str

    @abstractmethod
    def get_filename_by_time(self, time: datetime) -> Path:
        """Construct the filename containing a given time."""

    def get_filenames_by_time_range(
        self, start: datetime, stop: datetime
    ) -> List[Path]:
        """Find filenames which encompass a given time range.

        Iterates between start and stop by hour to construct a list of filenames
        but does not check for file existence.
        """
        filenames = []
        time = start
        while time <= stop:
            filenames.append(self.get_filename_by_time(time))
            time += timedelta(hours=1)

        # Cast to set then back to list to remove duplicates.
        return sorted(list(set(filenames)))


class HrrrSource(AbstractMeteorologySource):
    """GCS mirror for NOAA ARL HRRR data."""

    # https://console.cloud.google.com/storage/browser/high-resolution-rapid-refresh/noaa_arl_formatted
    artifact_bucket = "high-resolution-rapid-refresh"
    artifact_prefix = "noaa_arl_formatted"
    extent = GridExtent(xmin=-122.71902, xmax=-60.9162, ymin=12.1381, ymax=47.8419)
    hours_per_file = 6
    strptime_format = "%Y%m%d_%H"  # "20190530_12-17_hrrr"

    def get_filename_by_time(self, time: datetime) -> Path:
        time_first = time.replace(
            hour=int(time.hour / self.hours_per_file) * self.hours_per_file,
            minute=0,
            second=0,
            microsecond=0,
        )
        time_last = time_first + timedelta(hours=self.hours_per_file - 1)
        filename = f"{time_first.strftime(self.strptime_format)}-{time_last:%H}_hrrr"
        return Path(self.artifact_prefix) / filename


class HrrrForecastSource(AbstractMeteorologySource):
    """GSS mirror for NOAA ARL HRRR forecast data."""

    # https://console.cloud.google.com/storage/browser/high-resolution-rapid-refresh/noaa_arl_formatted/forecast
    # gs://high-resolution-rapid-refresh/noaa_arl_formatted/forecast/20211007/hysplit.t15z.hrrrf

    artifact_bucket = "high-resolution-rapid-refresh"
    artifact_prefix = "noaa_arl_formatted/forecast"
    extent = GridExtent(xmin=-122.71902, xmax=-60.9162, ymin=12.1381, ymax=47.8419)
    hours_per_file = 23
    strptime_format = "%Y%m%d/hysplit.t%Hz.hrrrf"  # 20210625/hysplit.t13z.hrrrf

    def get_filename_by_time(self, time: datetime) -> Path:
        time_first = time.replace(hour=time.hour, minute=0, second=0, microsecond=0)
        filename = time_first.strftime(self.strptime_format)
        return Path(self.artifact_prefix) / filename

    def get_filenames_by_time_range(
        self, start: datetime, stop: datetime
    ) -> List[Path]:
        """Find single file containing the full range of future times.

        Overrides the default method provided by parent class, since the time
        conventions for forecast data are different from reanalysis data. Since
        only a single file is used to drive forecast simulations, we find the
        newest file containing the time range necessary to fully execute a given
        simulation.
        """
        time_duration_seconds = (stop - start).seconds
        if time_duration_seconds > self.hours_per_file * 3600:
            raise ValueError(f"Supports time range up to {self.hours_per_file} hours.")

        # Since we only return a single file when using forecast data, and we know that
        # the simulation duration doesn't exceed what is contained within a single
        # file, just find a single filename using the start time.
        return [self.get_filename_by_time(start)]


class MeteorologyModel(str, Enum):
    """Available upstream meteorological sources."""

    HRRR = "hrrr"
    HRRR_FORECAST = "hrrr_forecast"


def meteorology_source_factory(model: MeteorologyModel) -> AbstractMeteorologySource:
    """Get a concrete MeteorologySource by name."""
    meteorology_model_mapper = {
        MeteorologyModel.HRRR: HrrrSource,
        MeteorologyModel.HRRR_FORECAST: HrrrForecastSource,
    }
    return meteorology_model_mapper[model]()


def _enforce_trailing_slash(string: str) -> str:
    """Ensure string ends in forward slash."""
    if string.endswith("/"):
        return string
    return f"{string}/"


def xtrct_grid(
    input_path: Path,
    output_path: Path,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    n_levels: int = None,
):
    """Export a cropped spatial subdomain from an ARL packed file."""
    # Requires >=0.4 degree padding between the parent domain extent and crop domain
    # extent on all sides or will fail reporting:
    #   At line 386 of file ../source/xtrct_grid.f
    #   Fortran runtime error: Bad value during integer read

    input_dirname = _enforce_trailing_slash(str(input_path.parent))
    input_basename = input_path.name
    # Fetch number of vertical levels contained in file from header.
    if not n_levels:
        with open(input_path, "rb") as f:
            metadata = f.read(166)
        n_levels = int(metadata[149:152])

    stdin = "\n".join(
        (
            input_dirname,
            input_basename,
            f"{ymin} {xmin}",
            f"{ymax} {xmax}",
            f"{n_levels}",
            "",
        )
    ).encode("utf-8")

    with tempfile.TemporaryDirectory() as xtrct_wd:
        logger.debug(f"Executing xtrct_grid: {input_basename}")
        proc = subprocess.run(
            XTRCT_GRID,
            input=stdin,
            cwd=xtrct_wd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        logger.info(f"Successfully executed xtrct_grid: {input_basename}")
        if proc.returncode != 0:
            raise XtrctGridException(proc.stdout + proc.stderr)

        # Default filename output by xtrct_grid fortran utility.
        extract_bin = Path(xtrct_wd) / "extract.bin"
        extract_bin.rename(output_path)


def xtrct_time(
    input_path: Path,
    output_path: Path,
    tmin: datetime,
    tmax: datetime,
):
    """Export a cropped time range from an ARL packed file."""
    # Runs xtrct_time twice since the start and stop record indexes are needed to
    # subset in time. These values are parsed from stdout from the first run and
    # passed as arguments to the second run.

    input_dirname = _enforce_trailing_slash(str(input_path.parent))
    input_basename = input_path.name

    stdin = "\n".join(
        (
            input_dirname,
            input_basename,
            f"{tmin:%d %H %M}",
            f"{tmax:%d %H %M}",
            "0",  # Skip every n times. Zero includes all times within range.
            # "1 1026",  # Start and stop record numbers.
        )
    )

    with tempfile.TemporaryDirectory() as xtrct_wd:
        logger.debug(f"Executing xtrct_time: {input_basename}")
        proc = subprocess.run(
            XTRCT_TIME,
            cwd=xtrct_wd,
            input=stdin.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        logger.info("Successfully executed xtrct_time.")

        # Append record indexes to stdin for subsequent xtrct_grid call.
        stdout_lines = proc.stdout.splitlines()
        start_record, stop_record = [
            int(x) for x in stdout_lines[-1].rsplit(None, 2)[-2:]
        ]
        if start_record <= 0 or stop_record <= 0:
            raise XtrctTimeException(f"Time range not found in {input_path}.")
        stdin += f"\n{start_record} {stop_record}\n"

        proc = subprocess.run(
            XTRCT_TIME,
            input=stdin.encode("utf-8"),
            cwd=xtrct_wd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            raise XtrctTimeException(proc.stdout + proc.stderr)

        # Default filename output by xtrct_grid fortran utility.
        extract_bin = Path(xtrct_wd) / "extract.bin"
        extract_bin.rename(output_path)


def crop_meteorology(
    input_paths: Iterable[Path],
    output_path: Path,
    xmin: float,
    xmax: float,
    ymin: float,
    ymax: float,
    tmin: datetime,
    tmax: datetime,
    n_levels: int = None,
):
    """Crop and concatenate ARL meteorological files.

    Args:
        input_paths (Iterable[str]): One or more files containing the full spatial
            and time extent specified.
        output_path (str): Destination filename to store cropped meteorological data,
            generated by subsetting and merging files specified in input_paths.
        xmin (float): Minimum longitude (left side) of subdomain.
        xmax (float): Maximum longitude (right side) of subdomain.
        ymin (float): Minimum latitude (bottom side) of subdomain.
        ymax (float): Maximum latitude (top side) of subdomain.
        tmin (datetime): Minimum time of subdomain, inclusive.
        tmax (datetime): Maximum time of subdomain, inclusive.
        n_levels (int, optional): Number of vertical levels above the surface to
            include, including the surface level. Defaults to None, which retains all
            levels.

    Raises:
        XtrctException: Non-zero exit code returned from HYSPLIT utilities.
    """
    input_paths = [path.resolve() for path in input_paths]
    with tempfile.TemporaryDirectory() as xtrct_wd:
        with tempfile.NamedTemporaryFile() as merged_file_obj:
            for path in input_paths:
                basename = path.name
                chunk_path = Path(xtrct_wd) / basename

                xtrct_grid(
                    input_path=path,
                    output_path=chunk_path,
                    xmin=xmin,
                    xmax=xmax,
                    ymin=ymin,
                    ymax=ymax,
                    n_levels=n_levels,
                )

                with open(chunk_path, "rb") as f:
                    merged_file_obj.write(f.read())

            xtrct_time(
                Path(merged_file_obj.name),
                output_path=output_path,
                tmin=tmin,
                tmax=tmax,
            )
