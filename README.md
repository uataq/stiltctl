# STILT control utilities

> Work in progress, provided as a minimal example.

## Introduction

The [STILT model](https://uataq.github.io/stilt/) is a popular extension of the [HYSPLIT](https://www.ready.noaa.gov/HYSPLIT.php) Lagrangian particle dispersion model that uses atmospheric simulations to estimate the impact of surface emissions on a downstream receptor location. STILT takes meteorological data and a receptor location and outputs a footprint representing the receptor's sensitivity to upstream emissions. Refer to the [STILT documentation](https://uataq.github.io/stilt/#/best-practices) for details about how the model is configured.

STILT's built in batch processing workflows work well for traditional use cases on HPC systems, where nodes are assumed to be reliable and sets of simulations generally succeed or fail as a single unit. However, operationalizing large quantities of simulations requires distributed, fault tolerant systems for reliable throughput. This is a minimal implementation to run STILT workloads at scale on Kubernetes, leveraging cost conscious compute and storage systems.

### Terminology

- **Scene**: a group of associated **simulations**, which could represent all of the simulations related to a single gridded satellite retrieval or all of the simulations over an arbitrary grid at a specified time.
- **Pixel**: consists of a single pixel or a collection of retrieved pixels, which are aggregated to coarsen their representative spatial scale. Each contains attributes for retrieved column methane concentration, viewing geometry, and forecast meteorology which provides wind and boundary layer characteristics.
- **Simulation config**: the configuration parameters used to tweak STILT's transport and dispersion methods. Configuration parameters often consist of shared attributes for a given **scene**.
- **Receptor**: the location and time (`x, y, z, t`) of interest, which represents the starting point of a time-backwards STILT simulation.
- **Trajectories**: the time resolved evolution of a particle ensemble traveling backward in time from the **receptor** location. STILT [natively outputs particle trajectories](https://uataq.github.io/stilt/#/output-files?id=particle-trajectories) as a data frame using the built in serialization format in R (`.rds`), which we selectively transform into parquet files for archival.
- **Footprint**: a grid of time resolved (`x, y, t`) or time integrated (`x, y`) sensitivities to fluxes, given as mole fraction per unit flux (`ppm / (umol m-2 s-1)`). STILT [natively outputs footprints](https://uataq.github.io/stilt/#/output-files?id=gridded-footprints) as NetCDF (`.nc`) files following the [CF convention](http://cfconventions.org).
- **Simulation**: the STILT process which is given a **receptor** and relevant **meteorology** and returns **trajectories** and **footprint**.
- **Meteorology**: meteorological model data in the ARL format, typically pulled from [NOAA ARL](https://www.ready.noaa.gov/archives.php) or user generated with the [WRF model](https://github.com/uataq/stilt-tutorials/tree/main/03-wrf). The HRRR model (3 km) is often the best data available for the continental US while the GFS (0.25 degree ~ 25 km at midlatitudes) can be used globally.
- **Meteorology Aggregate**: a single-file collection of **meteorology** data, cropped to the space-time domain required by a **simulation** (`x, y, z, t`) to minimize resource consumption. Aggregates are commonly shared among **simulations** of a **scene**.

## Development environment

STILT is only compatible with UNIX systems but may run under WSL. Dependencies include:

1. `postgres`
1. `docker`
1. `poetry`

> Poetry defaults to maintaining virtual environments externally. To configure poetry to create virtual environments in the project directory, first run `poetry config virtualenvs.in-project true`

Install `stiltctl` with development dependencies into a virtual environment with:

```bash
make install
```

To execute the tests, we need a `postgres` database used for job queues. Run the local development dependencies defined in `docker-compose.yaml` with:

```bash
make dependencies
```

You can run the tests using any of the following options:

1. `make ci`: check formatting, perform static analysis, and run tests.
1. `make test`: run only `pytest` to check functionality and print test coverage and profiling reports.
1. Use VSCode's built-in test runner for interactive development with the debugger.

## Infrastructure deployment

This example deploys to GCP but most of the implementation is provider agnostic. Terraform deploys a single GKE cluster with `dev` and `prod` namespaces to isolate environments.

The Terraform configuration also deploys Kubernetes resources resources to reference the deployed infrastructure, including:

1. A cluster-wide install of [KEDA](https://keda.sh).
1. A `db-secret` Kubernetes `Secret` in the `dev` and `prod` namespaces with `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, and `POSTGRES_CONNECTION` keys.
1. A `environment` Kubernetes `ConfigMap` in the `dev` and `prod` namespaces with `ENVIRONMENT`, `PROJECT`, `ARTIFACT_DRIVER`, and `ARTIFACT_BUCKET` keys.

Since database credentials are provisioned by Terraform during deployment, subsequent deployments will cycle passwords for the `dev` and `prod` Postgres instances.

> Our test project runs on a 500 vCPU GKE cluster, but this requires quota increases from GCP. The example Terraform configurations limit the cluster to 50 vCPUs

### Set application default credentials

> You'll need `gcloud` to point to an active configuration within an existing GCP project. See `gcloud init` and `gcloud config configurations list`.

Make sure that `gcloud` is configured to use application default credentials:

```bash
gcloud auth application-default login
```

Take a look in [terraform/main.tf](terraform/main.tf) to be sure you know what you're deploying. Set these environment variables and run the deploy script:

```bash
export PROJECT=<project_name>
export REGION=us-central1

make infra
```

## Service deployment

![](./docs/architecture.drawio.svg)

Set these environment variables and run the deploy script:

```bash
export PROJECT=<project_name>
export ENVIRONMENT=dev

make deploy
```

This deploys several services and a suspended `CronJob` specified in [helm/templates/scene-generator.yaml](helm/templates/scene-generator.yaml) that you can use as an example entrypoint. If you deployed to the `dev` environment as shown above, trigger the cronjob with:

```bash
kubectl -n dev create job scene-generator --from=cronjob/scene-generator
```

## Backlog

1. Add use case to pass upstream aggregated retrieval DTO to create a scene and associated STILT configurations (currently `DomainConfig.get_simulation_manifests`).
1. Using a scene's max PBLH, estimate the number of GFS vertical levels (sigma-pressure hybrid coordinates) required to run simulations (see `stiltctl.services.minimize_meteorology`).
1. Pass vertical weighting function into STILT to scale particle influence by retrieval sensitivity. This requires a PR to upstream [uataq/stilt](https://github.com/uataq/stilt) adding a `before_footprint_path` option to `stilt_cli.r`, which contains a function named `before_footprint` which can rescale particle sensitivity (`output$particle$foot`) based on retrieval characteristics (water vapor, pressure, averaging kernel, etc.). More generally, STILT's HPC interface provides `before_footprint` and `before_trajec` arguments which can inject arbitrary user code into strategic points in the simulation workflow (see the [STILT docs](https://uataq.github.io/stilt/#/configuration?id=inject-user-defined-functions) and the [implementation](https://github.com/uataq/stilt/blob/main/r/src/simulation_step.r#L349-L350)).
1. After all simulations of a scene are complete, materialize footprint jacobian for inverse model.
1. Harden for various failure modes.
1. KEDA should be namespace scoped to test version updates.
1. Default service accounts used here are overly permissive, should be revisited for production workloads.
1. Postgres instances currently allow public access (with password auth) for development. Probably better off connecting via the cloud SQL auth proxy mounted as a sidecar container in `stiltctl` service pods.
1. The Kubernetes cluster uses node auto-provisioning, which should be replaced with user defined node pools.
1. This example uses surface-based simulations and will need to be modified for column simulations. See `tests.test_simulations.test_column_simulation` for an example of how to construct a column receptor.

### Other notes

1. This implementation makes the use of sqlalchemy's imperative mapping (see [`stiltctl.database`](./stiltctl/database.py#146) and [`stiltctl.repositories`](./stiltctl/repositories.py#23)) which seems out of place in this stripped down example. While the code where this is useful is stipped out here (not relevant to MethaneSAT), the imperative mapper can instrument domain models with persistence logic such that they can be used natively with sqlalchemy's `session` (after calling `stiltctl.database.configure_mappers`). It avoids a separate domain -> persistence model mapping service for each database backed repository, and keeps domain models agnostic to their persistence mechanism.
1. We use postgres as a job queue instead of pulling in a message broker (previous implementations have used RabbitMQ, Redis, and GCP Pub/Sub). Since our workload is compute constrained, the required messaging throughput is relatively small (on the order of 10 read/write per second) and can be handled by a minimally specced Postgres instance. It's one less connection to manage, provides clean transactional semantics around enqueue/dequeue operations that can be committed alongside other state changes, has a better failure/backup story, and can guarantee exactly once processing of events. The main tradeoffs are your write throughput is constrained by how much you can vertically scale your Postgres instance (which is a lot), and modeling in fan-in DAG dependencies pushes complexity and orchestration logic into application services. If modeling DAG dependencies becomes a challenge, you might be better off with the Airflow/Argo/Dagster/Flyte/Prefects of the world.
   1. Postgres credentials are provisioned by Terraform and passwords are rotated on each deploy. If you want to tinker around in the database, shell into one of the running pods and extract the postgres credentials from the `POSTGRES_CONNECTION` environment variable.
