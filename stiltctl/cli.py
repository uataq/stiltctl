"""
Entrypoint to stiltctl command.

This module is just a thin wrapper that parses CLI arguments, loads
configuration relevant to each entrypoint, and calls out to application services
defined in stiltctl.services.
"""
import time
from pathlib import Path

import typer
import yaml
from loguru import logger
from pydantic import ValidationError

from stiltctl import events, services
from stiltctl.config import config_from_env
from stiltctl.dtos import DomainConfig
from stiltctl.exceptions import NotFound
from stiltctl.unit_of_work import unit_of_work_factory
from stiltctl.utils import timeout

app = typer.Typer()


def load_domain_configs(path: Path):
    """Load all yaml files in path matching the DomainConfig format."""
    paths = path.glob("*.yaml")
    if not paths:
        raise ValueError(f"No yaml files found in: {str(path)}")

    domain_configs = []
    for p in paths:
        logger.debug(f"Loading domain config from: {str(p)}")
        try:
            with open(p, "r") as f:
                domain_config = DomainConfig(**yaml.safe_load(f))
                domain_configs.append(domain_config)
                logger.info(
                    f"Parsed domain_config as: {domain_config.dict(exclude_defaults=True)}"
                )
        except ValidationError as e:
            logger.exception(e)
    return domain_configs


@app.command()
def generate_scenes(
    path: Path = typer.Argument(".", help="Path to domain config yaml files."),
):
    """Initialize scenes from domain configurations.

    Given a path to one or more <domain_name>.yaml files, validate the
    configurations and adds scene DomainConfigs to the events_scene_generated
    queue.
    """
    domain_configs = load_domain_configs(path)

    uow = unit_of_work_factory(config_from_env)
    for domain_config in domain_configs:
        with uow:
            with timeout(30):
                services.generate_scene_from_domain_config(
                    uow=uow, domain_config=domain_config
                )


@app.command()
def minimize_meteorology():
    """Generate a meteorology aggregate.

    Pulls a single DomainConfig from the events_simulation_generated queue, and
    use HYSPLIT's xtrct_grid and xtrct_time utilities to minimize and merge
    meteorological data. The generated meteorology aggregate is unique to a
    scene and contains a minimal representation of the space/time extent of a
    scene's simulations. Materializes the meteorology aggregate to object
    storage. On completion, adds the DomainConfig to the
    events_meteorology_minimized queue.
    """
    uow = unit_of_work_factory(config_from_env)

    with uow:
        event = uow.events.dequeue(events.SceneCreated)
        with timeout(1800):
            services.minimize_meteorology(uow, domain_config=event.domain_config)


@app.command()
def generate_simulations():
    """Initialize simulations from a scene's domain configurations.

    Pulls a single DomainConfig from the events_meteorology_minimized queue,
    constructs a SimulationManifest to represent the requested simulation
    configuration, and adds the SimulationManifests to the
    events_simulation_generated queue.
    """
    uow = unit_of_work_factory(config_from_env)
    with uow:
        event = uow.events.dequeue(events.MeteorologyMinimized)
        with timeout(1800):
            services.generate_simulations(uow, domain_config=event.domain_config)


@app.command()
def execute_simulations(
    exit_on_empty: bool = typer.Option(
        False, help="Return when queue is empty or block for additional simulations."
    )
):
    """Worker which execute simulations.

    Iterates over SimulationManifests from the events_simulation_generated
    queue, executes each simulation, and materializes results to object storage.
    """
    uow = unit_of_work_factory(config_from_env)
    while True:
        with uow:
            try:
                event = uow.events.dequeue(events.SimulationCreated)
            except NotFound:
                if exit_on_empty:
                    break
                else:
                    time.sleep(10)
                    continue

            with timeout(1800):
                services.execute_simulation(uow, simulation_manifest=event.manifest)


if __name__ == "__main__":
    app()
