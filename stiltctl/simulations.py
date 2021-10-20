import shutil
import subprocess
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Sequence, Tuple

from loguru import logger
from pydantic import BaseModel

from stiltctl.config import config_from_env
from stiltctl.exceptions import SimulationResultException, SimulationRuntimeException
from stiltctl.footprint import Footprint
from stiltctl.spatial import GridExtent, latitude_type, longitude_type

STILT_CLI = config_from_env.STILT_PATH / "r" / "stilt_cli.r"


class SimulationConfig(BaseModel):
    """Parameters passed to STILT/HYSPLIT.

    For parameter documentation, see:
        https://uataq.github.io/stilt/#/configuration

    Args:
        r_run_time (datetime): simulation start time
        r_lati (float): receptor latitude
        r_long (float): receptor longitude
        r_zagl (float): receptor height above ground in meters

        n_hours (int): simulation duration in hours
        xmn (float): footprint minimum longitude in -180:180
        xmx (float): footprint maximum longitude in -180:180
        xres (float): footprint longitude resolution
        ymn (float): footprint minimum latitude in -90:90
        ymx (float): footprint maximum latitude in -90:90
        yres (float): footprint latitude resolution
        time_integrate (bool): should footprints be summed across time; defaults true.
    """

    n_hours: int
    xmn: longitude_type
    xmx: longitude_type
    xres: float
    ymn: latitude_type
    ymx: latitude_type
    yres: float
    timeout: int = 60

    capemin: Optional[float] = None
    cmass: Optional[float] = None
    conage: Optional[float] = None
    cpack: Optional[float] = None
    dxf: Optional[float] = None
    dyf: Optional[float] = None
    dzf: Optional[float] = None
    efile: Optional[str] = None
    emisshrs: Optional[float] = None
    frhmax: Optional[float] = None
    frhs: Optional[float] = None
    frme: Optional[float] = None
    frmr: Optional[float] = None
    frts: Optional[float] = None
    frvs: Optional[float] = None
    hnf_plume: Optional[bool] = None
    horcoruverr: Optional[float] = None
    horcorzierr: Optional[float] = None
    hscale: Optional[float] = None
    ichem: Optional[float] = None
    idsp: Optional[float] = None
    initd: Optional[float] = None
    k10m: Optional[float] = None
    kagl: Optional[float] = None
    kbls: Optional[float] = None
    kblt: Optional[float] = None
    kdef: Optional[float] = None
    khinp: Optional[float] = None
    khmax: Optional[float] = None
    kmix0: Optional[float] = None
    kmixd: Optional[float] = None
    kmsl: Optional[float] = None
    kpuff: Optional[float] = None
    krand: Optional[float] = None
    krnd: Optional[float] = None
    kspl: Optional[float] = None
    kwet: Optional[float] = None
    kzmix: Optional[float] = None
    maxdim: Optional[float] = None
    maxpar: Optional[float] = None
    mgmin: Optional[float] = None
    n_met_min: Optional[float] = None
    ncycl: Optional[float] = None
    ndump: Optional[float] = None
    ninit: Optional[float] = None
    nstr: Optional[float] = None
    nturb: Optional[float] = None
    numpar: Optional[int] = None
    nver: Optional[float] = None
    outdt: Optional[float] = None
    outfrac: Optional[float] = None
    p10f: Optional[float] = None
    pinbc: Optional[str] = None
    pinpf: Optional[str] = None
    poutf: Optional[str] = None
    projection: Optional[str] = None
    qcycle: Optional[float] = None
    random: Optional[float] = None
    rhb: Optional[float] = None
    rht: Optional[float] = None
    rm_dat: Optional[bool] = None
    siguverr: Optional[float] = None
    sigzierr: Optional[float] = None
    smooth_factor: Optional[float] = None
    splitf: Optional[float] = None
    time_integrate: Optional[bool] = True
    tkerd: Optional[float] = None
    tkern: Optional[float] = None
    tlfrac: Optional[float] = None
    tluverr: Optional[float] = None
    tlzierr: Optional[float] = None
    tout: Optional[float] = None
    tratio: Optional[float] = None
    tvmix: Optional[float] = None
    varsiwant: Optional[str] = None
    veght: Optional[float] = None
    vscale: Optional[float] = None
    vscaleu: Optional[float] = None
    vscales: Optional[float] = None
    w_option: Optional[float] = None
    wbbh: Optional[float] = None
    wbwf: Optional[float] = None
    wbwr: Optional[float] = None
    wvert: Optional[bool] = None
    zicontroltf: Optional[float] = None
    ziscale: Optional[float] = None
    z_top: Optional[float] = None
    zcoruverr: Optional[float] = None

    @property
    def footprint_extent(self) -> GridExtent:
        """Latitude and longitude bounding box for STILT footprints."""
        return GridExtent(xmin=self.xmn, xmax=self.xmx, ymin=self.ymn, ymax=self.ymx)


class AbstractReceptor(BaseModel, ABC):
    """Abstract base receptor controls the simulation start location and time.

    Subclasses should implement the to_stilt_kwargs method to construct a dict
    of STILT compatible arguments for each concrete receptor type. See:
    https://uataq.github.io/stilt/#/configuration
    """

    time: datetime
    longitude: Any
    latitude: Any
    height: Any

    key_mapper = {
        "time": "r_run_time",
        "longitude": "r_long",
        "latitude": "r_lati",
        "height": "r_zagl",
    }

    @property
    @abstractmethod
    def id(self) -> str:
        """Return unique hash for receptor."""

    @abstractmethod
    def to_stilt_kwargs(self) -> dict[str, Any]:
        """Cast attributes to stilt_cli compatible argument dictionary."""


class SurfaceReceptor(AbstractReceptor):
    """Location and time of simulation ensemble release."""

    time: datetime
    longitude: longitude_type
    latitude: latitude_type
    height: int = 1

    @property
    def id(self) -> str:
        return "/".join(
            (
                self.time.strftime("%Y-%m-%dT%H-%M-%S"),
                f"{self.longitude}",
                f"{self.latitude}",
                f"{self.height}",
            )
        )

    def to_stilt_kwargs(self):
        value_mapper = {
            "time": self.time.isoformat(),
            "longitude": self.longitude,
            "latitude": self.latitude,
            "height": self.height,
        }
        return {self.key_mapper[k]: value_mapper[k] for k in self.key_mapper.keys()}


class ColumnReceptor(AbstractReceptor):
    """Uniformly distributed line source for simulation ensemble release."""

    time: datetime
    longitude: Tuple[longitude_type, longitude_type]
    latitude: Tuple[latitude_type, latitude_type]
    height: Tuple[int, int]

    @property
    def id(self) -> str:
        return "/".join(
            (
                self.time.strftime("%Y-%m-%dT%H-%M-%S"),
                f"{self.longitude[0]}_{self.longitude[1]}",
                f"{self.latitude[0]}_{self.latitude[1]}",
                f"{self.height[0]}_{self.height[1]}",
            )
        )

    @staticmethod
    def _to_comma_delimited_string(fields: Sequence[Any]) -> str:
        return ",".join(str(x) for x in fields)

    def to_stilt_kwargs(self):
        value_mapper = {
            "time": self.time.isoformat(),
            "longitude": self._to_comma_delimited_string(self.longitude),
            "latitude": self._to_comma_delimited_string(self.latitude),
            "height": self._to_comma_delimited_string(self.height),
        }
        return {self.key_mapper[k]: value_mapper[k] for k in self.key_mapper.keys()}


class Simulation:
    def __init__(
        self,
        receptor: AbstractReceptor,
        config: SimulationConfig,
        meteorology_path: Path,
    ):
        """Generate STILT simulations using various configurations.

        Args:
            receptor (AbstractReceptor): Location and time to start the simulation.
            config (SimulationConfig): Key value parameters controlling the transport
                and dispersion settings.
            meteorology_path (Optional[str], optional): Local path to a
                meteorological file, used to drive the particle transport.
        """
        self.receptor = receptor
        self.config = config
        self.meteorology_path = meteorology_path
        self.stdout = b""
        self.stderr = b""
        self.footprint: Optional[Footprint] = None
        self.footprint_image: Optional[bytes] = None

    @property
    def id(self) -> str:
        """Get the unique id of the configured receptor."""
        return self.receptor.id

    def execute(self, image_kwargs: Optional[dict[str, Any]] = None):
        """Fetch required model input data and execute job

        Args:
            image_kwargs (Optional[dict[str, Any]]): Arguments passed to
                matplotlib.imshow for visualizations. Defaults to None.

        Raises:
            SimulationResultException: error getting valid simulation result.
        """
        self._call_stilt_cli()

        if self.footprint_path.exists():
            footprint = Footprint.from_path(self.footprint_path)
            image_kwargs = image_kwargs or dict(
                log10=True, cmap="BuPu", vmin=-4, vmax=0
            )
            footprint_image = footprint.create_image(**image_kwargs)

            self.footprint = footprint
            self.footprint_image = footprint_image
        else:
            messages = [message.decode() for message in (self.stdout, self.stderr)]
            stilt_log = self._get_stilt_log()
            if stilt_log:
                messages.append(stilt_log)
            else:
                messages.append(f"{self.log_path} not found.")
            raise SimulationResultException("\n\n".join(messages))

    def cleanup(self):
        """Remove files produced by this simulation."""
        shutil.rmtree(self.execution_path)

    def _call_stilt_cli(self):
        """Execute stilt_cli.r with timeout."""
        logger.debug(f'Executing: {" ".join(self._stilt_cli_command)}')
        try:
            proc = subprocess.run(
                self._stilt_cli_command,
                capture_output=True,
                # Pad STILT timeout by 10 s to first allow STILT's internal
                # mechanisms to gracefully exit before the process is killed.
                timeout=self.config.timeout + 10,
            )
            self.stdout = proc.stdout
            self.stderr = proc.stderr
        except subprocess.TimeoutExpired:
            subprocess.run(["pkill", "-f", "hycs_std"])
            raise SimulationRuntimeException("Timeout exceeded.")

    def _get_stilt_log(self) -> Optional[str]:
        """Load the stilt.log file dumped by hycs_std."""
        if not self.log_path.exists():
            return None
        with open(self.log_path, "r") as f:
            return f.read()

    @property
    def _stilt_cli_command(self) -> list[str]:
        """Construct CLI command from receptor and config."""
        stilt_kwargs = {
            **self.config.dict(),
            **self.receptor.to_stilt_kwargs(),
            "met_file_format": self.meteorology_path.name,
            "met_path": str(self.meteorology_path.parent),
            "stilt_wd": config_from_env.STILT_PATH,
            "simulation_id": "default",
        }

        command = [str(STILT_CLI)]
        for key, value in stilt_kwargs.items():
            if value is None:
                continue
            elif isinstance(value, bool):
                value = "T" if value else "F"
            elif isinstance(value, float):
                value = round(value, 8)

            command.append(f"{key}={value}")

        return command

    @property
    def execution_path(self) -> Path:
        """Working directory for simulation assets."""
        execution_path = config_from_env.STILT_PATH / "out" / "by-id" / "default"
        execution_path.mkdir(parents=True, exist_ok=True)
        return execution_path

    @property
    def footprint_path(self) -> Path:
        return self.execution_path / f"default_foot.nc"

    @property
    def trajectory_path(self) -> Path:
        return self.execution_path / f"default_traj.rds"

    @property
    def log_path(self) -> Path:
        return self.execution_path / "stilt.log"
