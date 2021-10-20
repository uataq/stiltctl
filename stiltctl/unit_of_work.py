from typing import Optional, Type

from cloudstorage import Container  # type: ignore
from loguru import logger
from sqlalchemy.future.engine import Engine  # type: ignore
from sqlalchemy.orm.session import Session, sessionmaker

from stiltctl.config import StiltctlConfig
from stiltctl.database import configure_mappers, create_schema, engine_factory
from stiltctl.events import Event
from stiltctl.exceptions import StiltException
from stiltctl.repositories import EventQueue, SceneRepository, SimulationRepository
from stiltctl.storage import get_bucket


class UnitOfWork:
    def __init__(self, engine: Engine, artifact_bucket: Container):
        self.artifact_bucket = artifact_bucket
        self.artifact_driver = artifact_bucket.driver

        self.engine = engine
        self.session_factory = sessionmaker(bind=engine)
        self._session: Optional[Session] = None

    @property
    def session(self) -> Session:
        if not self._session:
            raise Exception("session cannot be accessed outside of context manager")
        return self._session

    @property
    def events(self) -> EventQueue:
        return EventQueue(self.session)

    @property
    def simulations(self) -> SimulationRepository:
        return SimulationRepository(bucket=self.artifact_bucket)

    @property
    def scenes(self) -> SceneRepository:
        return SceneRepository(self.session)

    def __enter__(self):
        self._session = self.session_factory()
        return self

    def __exit__(self, exception_type: Type, exception_value: Exception, traceback):
        if exception_type is None:
            self.session.commit()
        elif exception_type is StiltException:
            self.session.commit()
            logger.exception(exception_value)
        else:
            self.session.rollback()

        self.session.close()
        self._session = None


def unit_of_work_factory(config: StiltctlConfig) -> UnitOfWork:
    """Construct UnitOfWork from environment variable configuration."""
    artifact_bucket = get_bucket(config.ARTIFACT_BUCKET, config.ARTIFACT_DRIVER)

    engine = engine_factory(
        f"postgresql+psycopg2://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}"
        f"@{config.POSTGRES_HOST}:5432/postgres"
    )
    configure_mappers()
    create_schema(engine)

    return UnitOfWork(engine=engine, artifact_bucket=artifact_bucket)
