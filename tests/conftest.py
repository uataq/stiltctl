import shutil
from pathlib import Path
from typing import Generator

import pytest  # type: ignore
from cloudstorage import DriverName  # type: ignore
from sqlalchemy.orm import clear_mappers

from stiltctl.config import config_from_env
from stiltctl.database import healthcheck, reset_schema
from stiltctl.unit_of_work import UnitOfWork, unit_of_work_factory


@pytest.fixture(scope="session", autouse=True)
def seed_storage():
    if config_from_env.ARTIFACT_DRIVER == DriverName.LOCAL:
        storage_path = ".cloudstorage"
        shutil.rmtree(storage_path, ignore_errors=True)

        seed_buckets = Path(__file__).resolve().parent / "data" / "buckets"
        shutil.copytree(seed_buckets, storage_path)

        (Path(storage_path) / config_from_env.ARTIFACT_BUCKET).mkdir(
            parents=True, exist_ok=True
        )
        assert Path(".cloudstorage").exists()


@pytest.fixture(scope="session", autouse=True)
def uow() -> Generator[UnitOfWork, None, None]:
    uow = unit_of_work_factory(config_from_env)

    if not healthcheck(uow.engine):
        raise EnvironmentError("Database not running. Run 'make dependencies'.")

    if "localhost" in config_from_env.POSTGRES_HOST:
        reset_schema(uow.engine)

    yield uow
    clear_mappers()
