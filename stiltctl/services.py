"""
These application services specify handlers for each Command or Event class. but what
this gets reall test making this way too long
"""
from pathlib import Path

from cloudstorage.exceptions import NotFoundError  # type: ignore
from loguru import logger

from stiltctl import events
from stiltctl.config import config_from_env
from stiltctl.dtos import DomainConfig, SimulationManifest
from stiltctl.exceptions import MeteorologyNotFound
from stiltctl.meteorology import crop_meteorology, meteorology_source_factory
from stiltctl.repositories import SceneRecord
from stiltctl.simulations import Simulation
from stiltctl.storage import get_bucket
from stiltctl.unit_of_work import UnitOfWork


def generate_scene_from_domain_config(uow: UnitOfWork, domain_config: DomainConfig):
    """Publish new scenes to the queue."""
    scene = SceneRecord(
        scene_id=domain_config.scene_id,
        successful_simulations=0,
        total_simulations=len(domain_config.receptor_grid.to_points()),
    )
    uow.scenes.add(scene)
    logger.success(
        f"Generated scene from domain_config: {domain_config.dict(exclude_defaults=True)}"
    )

    logger.debug(
        f"Publishing domain_config: {domain_config.dict(exclude_defaults=True)}"
    )
    uow.events.add(events.SceneCreated(domain_config=domain_config))


def minimize_meteorology(uow: UnitOfWork, domain_config: DomainConfig):
    """Generate a meteorology aggregate."""
    meteorology_extent = domain_config.get_meteorology_extent()
    logger.info(
        f"Cropping meteorology for: {domain_config.dict(exclude_defaults=True)}"
        f" to: {meteorology_extent}"
    )

    meteorology_source = meteorology_source_factory(domain_config.meteorology_model)
    meteorology_filenames = meteorology_source.get_filenames_by_time_range(
        meteorology_extent.tmin, meteorology_extent.tmax
    )
    meteorology_source_bucket = get_bucket(
        meteorology_source.artifact_bucket, config_from_env.ARTIFACT_DRIVER
    )

    # Since we're calling out to HYSPLIT executables, we need temporary
    # filesystem locations to pass data between python and fortran. We use a
    # temporary directory to pull down the required meteorological file(s).
    cropped_meteorology_path = Path("/tmp/meteorology.arl")

    input_paths = []
    for meteorology_filename in meteorology_filenames:
        meteorology_basename = meteorology_filename.name
        input_path = Path("/tmp") / meteorology_basename

        logger.debug(f"Downloading: {str(meteorology_filename)}")
        try:
            blob = meteorology_source_bucket.get_blob(str(meteorology_filename))
            blob.download(input_path)
        except NotFoundError as e:
            raise MeteorologyNotFound(str(e))
        input_paths.append(input_path)
        logger.info(f"Download successful: {str(meteorology_filename)}")

    logger.debug(
        f"Cropping meteorology from: {[str(x) for x in input_paths]} "
        f"to: {cropped_meteorology_path}"
    )
    crop_meteorology(
        input_paths,
        cropped_meteorology_path,
        **meteorology_extent.dict(),
        # TODO: select n_levels based on max PBLH within the domain.
        n_levels=20,
    )
    logger.info(f"Crop successful: {cropped_meteorology_path}")

    logger.debug(
        "Uploading meteorology to: "
        f"{config_from_env.ARTIFACT_BUCKET}/by-scene-id/{domain_config.scene_id}"
    )
    uow.artifact_bucket.upload_blob(
        "/tmp/meteorology.arl",
        f"by-scene-id/{domain_config.scene_id}/meteorology.arl",
    )

    uow.events.add(events.MeteorologyMinimized(domain_config=domain_config))
    logger.info(f"Meteorology processing successful: {domain_config.scene_id}")


def generate_simulations(uow: UnitOfWork, domain_config: DomainConfig):
    """Publish simulations to queue for execution."""
    logger.debug(
        "Generating simulation manifests for domain_config: "
        f"{domain_config.dict(exclude_defaults=True)}"
    )
    simulation_manifests = domain_config.get_simulation_manifests()

    logger.debug(f"Generated simulations: {len(simulation_manifests)}")
    uow.events.add_many(
        [
            events.SimulationCreated(manifest=manifest)
            for manifest in simulation_manifests
        ]
    )
    logger.success(
        f"Added simulations to event_simulation_generated: {len(simulation_manifests)}"
    )


def execute_simulation(uow: UnitOfWork, simulation_manifest: SimulationManifest):
    """Setup and run simulation."""
    scene_id = simulation_manifest.scene_id

    meteorology_path = Path(f"/tmp/{scene_id}.arl")
    if not meteorology_path.exists():
        logger.info(
            f"Downloading meteorology: "
            f"gs://{config_from_env.ARTIFACT_BUCKET}/by-scene-id/"
            f"{scene_id}/meteorology.arl"
        )
        try:
            blob = uow.artifact_bucket.get_blob(
                f"by-scene-id/{scene_id}/meteorology.arl"
            )
            blob.download(meteorology_path)
        except NotFoundError as e:
            raise MeteorologyNotFound(e)

    logger.debug(
        f"Received manifest: {simulation_manifest.dict(exclude_defaults=True)}"
    )
    simulation = Simulation(
        config=simulation_manifest.config,
        receptor=simulation_manifest.receptor,
        meteorology_path=meteorology_path,
    )
    simulation.execute()
    logger.info(f"Simulation execution successful: {simulation.receptor.id}")
    uow.simulations.add(simulation)
    logger.success(f"Uploaded simulation artifacts: {simulation.receptor.id}")

    scene = uow.scenes.get(scene_id, lock_for_update=True)
    scene.successful_simulations = scene.successful_simulations + 1
    logger.info(
        "Scene completion: "
        f"{scene.successful_simulations}/{scene.total_simulations} "
        f"({scene.successful_simulations/scene.total_simulations * 100:.1f}%)"
    )
    # if (scene.total_simulations - scene.successful_simulations) == 0:
    #     # Scene has completed successfully. Dispatch an event to construct a
    #     # row oriented jacobian for the inversion service.
    #     ...
