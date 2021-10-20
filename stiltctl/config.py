"""
Parse configuration from environment variables.
"""
from pathlib import Path
from typing import Literal

from cloudstorage import DriverName  # type: ignore
from dotenv import load_dotenv
from pydantic import BaseSettings, validator


class StiltctlConfig(BaseSettings):
    ARTIFACT_DRIVER: DriverName
    ARTIFACT_BUCKET: str

    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str

    STILT_PATH: Path = Path("/usr/local/stilt")

    # LOGURU_LEVEL is recognized automatically when set but we include it here for
    # runtime validation.
    LOGURU_LEVEL: Literal[
        "TRACE", "DEBUG", "INFO", "SUCCESS", "WARNING", "ERROR", "CRITICAL"
    ] = "INFO"

    @validator("*", pre=True, always=True)
    def strip_quotes(cls, value: str) -> str:
        if isinstance(value, str):
            value = value.strip('"')
        return value


# .env.local is omitted from docker images.
load_dotenv(Path(__file__).parent.parent / ".env.local")

config_from_env = StiltctlConfig()
