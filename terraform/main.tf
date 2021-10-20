# terraform {
#   backend "gcs" {
#     bucket = "${lower(var.project)}-tfstate"
#   }

#   required_providers {
#     google = {
#       source  = "hashicorp/google"
#       version = "~> 3.87"
#     }
#   }
# }


provider "google" {
  project = lower(var.project)
  region  = lower(var.region)
}

provider "google-beta" {
  project = lower(var.project)
  region  = lower(var.region)
}


resource "google_container_registry" "main" {
  project = lower(var.project)
}


resource "google_container_cluster" "main" {
  provider = google-beta
  name     = lower(var.project)
  location = lower(var.region)

  initial_node_count = 1 # per zone

  release_channel {
    channel = "REGULAR"
  }

  maintenance_policy {
    daily_maintenance_window {
      start_time = "10:00"
    }
  }

  node_config {
    machine_type = "n2-standard-2"
    oauth_scopes = [
      "https://www.googleapis.com/auth/cloud-platform"
    ]
    disk_type = "pd-balanced"
  }

  cluster_autoscaling {
    enabled             = true
    autoscaling_profile = "OPTIMIZE_UTILIZATION"

    resource_limits {
      resource_type = "cpu"
      minimum       = 2
      maximum       = 50
    }
    resource_limits {
      resource_type = "memory"
      minimum       = 8
      maximum       = 100
    }

    auto_provisioning_defaults {
      oauth_scopes = [
        "https://www.googleapis.com/auth/cloud-platform"
      ]
    }
  }
}


resource "google_sql_database_instance" "dev" {
  name             = "${var.project}-stiltctl-dev"
  database_version = "POSTGRES_13"
  region           = "us-central1"

  settings {
    tier              = "db-custom-1-3840"
    availability_type = "ZONAL"
    backup_configuration {
      enabled = false
    }
    ip_configuration {
      authorized_networks {
        name  = "Public"
        value = "0.0.0.0/0"
      }
    }
    database_flags {
      name  = "max_connections"
      value = 500 # default: 100
    }
  }
}

resource "google_sql_database_instance" "prod" {
  name             = "${var.project}-stiltctl-prod"
  database_version = "POSTGRES_13"
  region           = "us-central1"

  settings {
    tier              = "db-custom-2-7680"
    availability_type = "REGIONAL"
    backup_configuration {
      enabled = true
    }
    ip_configuration {
      authorized_networks {
        name  = "Public"
        value = "0.0.0.0/0"
      }
    }
    database_flags {
      name  = "max_connections"
      value = 800 # default: 400
    }
  }
}


resource "random_password" "dev" {
  length  = 32
  special = false
}

resource "random_password" "prod" {
  length  = 32
  special = false
}


resource "google_sql_user" "dev" {
  name     = lower(var.project)
  instance = google_sql_database_instance.dev.name
  password = random_password.dev.result
}

resource "google_sql_user" "prod" {
  name     = lower(var.project)
  instance = google_sql_database_instance.prod.name
  password = random_password.prod.result
}


resource "google_storage_bucket" "dev" {
  name     = "${var.project}-dev"
  location = lower(var.region)
}

resource "google_storage_bucket" "prod" {
  name     = "${var.project}-prod"
  location = lower(var.region)
}


data "google_client_config" "provider" {}


provider "kubernetes" {
  host  = "https://${google_container_cluster.main.endpoint}"
  token = data.google_client_config.provider.access_token
  cluster_ca_certificate = base64decode(
    google_container_cluster.main.master_auth[0].cluster_ca_certificate,
  )
}


resource "kubernetes_namespace" "dev" {
  metadata {
    name = "dev"
  }
}

resource "kubernetes_namespace" "prod" {
  metadata {
    name = "prod"
  }
}


resource "kubernetes_secret" "db_dev" {
  metadata {
    name      = "db-secret"
    namespace = "dev"
  }

  data = {
    POSTGRES_USER       = lower(var.project)
    POSTGRES_PASSWORD   = random_password.dev.result
    POSTGRES_HOST       = google_sql_database_instance.dev.public_ip_address
    POSTGRES_CONNECTION = "postgresql://${lower(var.project)}:${random_password.dev.result}@${google_sql_database_instance.dev.public_ip_address}:5432/postgres"
  }
}

resource "kubernetes_secret" "db_prod" {
  metadata {
    name      = "db-secret"
    namespace = "prod"
  }

  data = {
    POSTGRES_USER       = lower(var.project)
    POSTGRES_PASSWORD   = random_password.prod.result
    POSTGRES_HOST       = google_sql_database_instance.prod.public_ip_address
    POSTGRES_CONNECTION = "postgresql://${lower(var.project)}:${random_password.prod.result}@${google_sql_database_instance.prod.public_ip_address}:5432/postgres"
  }
}


resource "kubernetes_config_map" "env_dev" {
  metadata {
    name      = "environment"
    namespace = "dev"
  }

  data = {
    ENVIRONMENT     = "dev"
    PROJECT         = lower(var.project)
    ARTIFACT_DRIVER = "GOOGLESTORAGE"
    ARTIFACT_BUCKET = google_storage_bucket.dev.name
  }
}

resource "kubernetes_config_map" "env_prod" {
  metadata {
    name      = "environment"
    namespace = "prod"
  }

  data = {
    ENVIRONMENT     = "prod"
    PROJECT         = lower(var.project)
    ARTIFACT_DRIVER = "GOOGLESTORAGE"
    ARTIFACT_BUCKET = google_storage_bucket.prod.name
  }
}

provider "helm" {
  kubernetes {
    host  = "https://${google_container_cluster.main.endpoint}"
    token = data.google_client_config.provider.access_token
    cluster_ca_certificate = base64decode(
      google_container_cluster.main.master_auth[0].cluster_ca_certificate,
    )
  }
}


resource "helm_release" "keda" {
  name       = "keda"
  repository = "https://kedacore.github.io/charts"
  chart      = "keda"
  version    = "2.4.0"

  namespace        = "keda"
  create_namespace = true
}
