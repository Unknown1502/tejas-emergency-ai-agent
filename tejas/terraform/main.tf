# ==========================================================================
# Tejas -- Terraform Infrastructure Configuration
#
# Provisions the Google Cloud resources required to run the Tejas
# emergency scene intelligence agent:
#
# - Cloud Run service (backend)
# - Firestore database
# - Cloud Storage bucket (scene captures)
# - Secret Manager secrets
# - IAM bindings
# - Artifact Registry repository
# ==========================================================================

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  # Remote state backend — enables safe team collaboration and state locking.
  # To enable:
  #   1. Create the bucket manually:  gsutil mb gs://YOUR_PROJECT_ID-tejas-tf-state
  #   2. Uncomment the block below and replace the bucket name.
  #   3. Run: terraform init  (will migrate existing local state)
  #
  # backend "gcs" {
  #   bucket = "YOUR_PROJECT_ID-tejas-tf-state"
  #   prefix = "terraform/state"
  # }
}

# --------------------------------------------------------------------------
# Provider
# --------------------------------------------------------------------------

provider "google" {
  project = var.project_id
  region  = var.region
}

# --------------------------------------------------------------------------
# Enable Required APIs
# --------------------------------------------------------------------------

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com",
    "compute.googleapis.com",
  ])

  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# --------------------------------------------------------------------------
# Service Account
# --------------------------------------------------------------------------

resource "google_service_account" "tejas" {
  account_id   = "tejas-backend"
  display_name = "Tejas Backend Service Account"
  project      = var.project_id
}

# Grant the service account required roles
resource "google_project_iam_member" "tejas_roles" {
  for_each = toset([
    "roles/datastore.user",
    "roles/storage.objectAdmin",
    "roles/secretmanager.secretAccessor",
    "roles/aiplatform.user",
    "roles/logging.logWriter",
    "roles/monitoring.metricWriter",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.tejas.email}"
}

# --------------------------------------------------------------------------
# Artifact Registry
# --------------------------------------------------------------------------

resource "google_artifact_registry_repository" "tejas" {
  location      = var.region
  repository_id = "tejas"
  format        = "DOCKER"
  description   = "Container images for the Tejas application"

  depends_on = [google_project_service.apis["artifactregistry.googleapis.com"]]
}

# --------------------------------------------------------------------------
# Firestore
# --------------------------------------------------------------------------

resource "google_firestore_database" "tejas" {
  project     = var.project_id
  name        = "(default)"
  location_id = var.firestore_location
  type        = "FIRESTORE_NATIVE"

  depends_on = [google_project_service.apis["firestore.googleapis.com"]]
}

# --------------------------------------------------------------------------
# Cloud Storage
# --------------------------------------------------------------------------

resource "google_storage_bucket" "scene_captures" {
  name     = "${var.project_id}-tejas-captures"
  location = var.region
  project  = var.project_id

  uniform_bucket_level_access = true
  force_destroy               = true

  lifecycle_rule {
    condition {
      age = 30
    }
    action {
      type = "Delete"
    }
  }

  depends_on = [google_project_service.apis["storage.googleapis.com"]]
}

# --------------------------------------------------------------------------
# Secret Manager
# --------------------------------------------------------------------------

resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = "tejas-gemini-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

# Google Maps API key for the get_nearest_hospital tool (Places API)
resource "google_secret_manager_secret" "google_maps_api_key" {
  secret_id = "tejas-google-maps-api-key"
  project   = var.project_id

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis["secretmanager.googleapis.com"]]
}

# Note: Secret values (actual key material) must be set manually and are
# never stored in Terraform state:
#   echo -n 'YOUR_GEMINI_KEY' | gcloud secrets versions add tejas-gemini-api-key --data-file=-
#   echo -n 'YOUR_MAPS_KEY'   | gcloud secrets versions add tejas-google-maps-api-key --data-file=-

# --------------------------------------------------------------------------
# Cloud Run -- Backend
# --------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "backend" {
  name     = "tejas-backend"
  location = var.region
  project  = var.project_id

  template {
    service_account = google_service_account.tejas.email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/tejas/backend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = var.cpu_limit
          memory = var.memory_limit
        }
      }

      env {
        name  = "ENVIRONMENT"
        value = var.environment
      }
      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "GCP_REGION"
        value = var.region
      }
      env {
        name  = "USE_VERTEX_AI"
        value = "true"
      }
      env {
        name  = "GCS_BUCKET_NAME"
        value = google_storage_bucket.scene_captures.name
      }
      env {
        # Comma-separated JSON array of allowed frontend origins.
        # Update var.frontend_url after the frontend Cloud Run service is deployed.
        name  = "ALLOWED_ORIGINS"
        value = var.frontend_url != "" ? "[\"${var.frontend_url}\",\"http://localhost:5173\"]" : "[\"http://localhost:5173\",\"http://localhost:3000\"]"
      }

      # Gemini API key from Secret Manager
      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      # Google Maps API key for hospital proximity search (optional)
      env {
        name = "GOOGLE_MAPS_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.google_maps_api_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        initial_delay_seconds = 5
        period_seconds        = 10
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
        period_seconds    = 30
        failure_threshold = 3
      }
    }

    # WebSocket sessions require long-lived connections
    timeout = "3600s"

    # Session affinity for WebSocket
    session_affinity = true
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_project_iam_member.tejas_roles,
    google_artifact_registry_repository.tejas,
  ]
}

# Allow unauthenticated access (the WebSocket handles its own auth)
resource "google_cloud_run_v2_service_iam_member" "public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.backend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --------------------------------------------------------------------------
# Cloud Run -- Frontend
# --------------------------------------------------------------------------

resource "google_cloud_run_v2_service" "frontend" {
  name     = "tejas-frontend"
  location = var.region
  project  = var.project_id

  template {
    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/tejas/frontend:latest"

      ports {
        container_port = 80
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "256Mi"
        }
      }

      # BACKEND_URL is injected at nginx startup via envsubst in the Dockerfile CMD.
      env {
        name  = "BACKEND_URL"
        value = google_cloud_run_v2_service.backend.uri
      }
    }
  }

  traffic {
    type    = "TRAFFIC_TARGET_ALLOCATION_TYPE_LATEST"
    percent = 100
  }

  depends_on = [
    google_project_service.apis["run.googleapis.com"],
    google_artifact_registry_repository.tejas,
    google_cloud_run_v2_service.backend,
  ]
}

resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# --------------------------------------------------------------------------
# Outputs
# --------------------------------------------------------------------------

output "backend_url" {
  description = "URL of the deployed Cloud Run backend service"
  value       = google_cloud_run_v2_service.backend.uri
}

output "frontend_url" {
  description = "URL of the deployed Cloud Run frontend service"
  value       = google_cloud_run_v2_service.frontend.uri
}

output "websocket_url" {
  description = "WebSocket URL for direct client connections to the backend"
  value       = "${replace(google_cloud_run_v2_service.backend.uri, "https://", "wss://")}/ws/stream"
}

output "service_account_email" {
  description = "Email of the Tejas service account"
  value       = google_service_account.tejas.email
}

output "artifact_registry" {
  description = "Artifact Registry repository path"
  value       = "${var.region}-docker.pkg.dev/${var.project_id}/tejas"
}

output "storage_bucket" {
  description = "Cloud Storage bucket for scene captures"
  value       = google_storage_bucket.scene_captures.name
}

output "firestore_database" {
  description = "Firestore database name"
  value       = google_firestore_database.tejas.name
}

output "next_steps" {
  description = "Post-deploy setup commands"
  value       = <<-EOT
    After terraform apply, run these commands:

    1. Set Gemini API key:
       echo -n 'YOUR_KEY' | gcloud secrets versions add tejas-gemini-api-key \
         --data-file=- --project=${var.project_id}

    2. Set Google Maps API key (optional):
       echo -n 'YOUR_MAPS_KEY' | gcloud secrets versions add tejas-google-maps-api-key \
         --data-file=- --project=${var.project_id}

    3. Seed reference data:
       curl -X POST ${google_cloud_run_v2_service.backend.uri}/api/seed

    4. Update ALLOWED_ORIGINS with frontend URL, then:
       terraform apply -var="frontend_url=${google_cloud_run_v2_service.frontend.uri}"
  EOT
}
