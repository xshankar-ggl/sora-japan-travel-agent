# ============================================================================
# Infrastructure as Code (IaC) for Sora — Japan-Specialist Travel Planning Agent
# Provisions GCP APIs, Least-Privilege IAM Service Account, Secret Manager,
# Artifact Registry, and Cloud Run v2 Service with OpenTelemetry & Secret Mounting.
# ============================================================================

locals {
  required_apis = toset([
    "run.googleapis.com",
    "aiplatform.googleapis.com",
    "secretmanager.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudtrace.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
  ])
}

resource "google_project_service" "enabled_apis" {
  for_each           = local.required_apis
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# Dedicated Least-Privilege Service Account for Sora Agent
resource "google_service_account" "sora_agent_sa" {
  account_id   = "sora-agent-runtime-sa"
  display_name = "Sora Japan Travel Agent Runtime Service Account"
  description  = "Least-privilege runtime identity for Sora ADK Agent on Cloud Run."
  depends_on   = [google_project_service.enabled_apis]
}

# IAM Bindings: Vertex AI, Cloud Trace, Cloud Logging
resource "google_project_iam_member" "vertex_ai_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.sora_agent_sa.email}"
}

resource "google_project_iam_member" "cloud_trace_agent" {
  project = var.project_id
  role    = "roles/cloudtrace.agent"
  member  = "serviceAccount:${google_service_account.sora_agent_sa.email}"
}

resource "google_project_iam_member" "structured_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.sora_agent_sa.email}"
}

# Dedicated Google Cloud Secret Manager Secret for Gemini API Key
resource "google_secret_manager_secret" "gemini_api_key" {
  secret_id = var.gemini_secret_id

  replication {
    auto {}
  }

  labels = {
    app       = "sora-japan-travel-agent"
    managedBy = "terraform"
  }

  depends_on = [google_project_service.enabled_apis]
}

resource "google_secret_manager_secret_iam_member" "sora_secret_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.gemini_api_key.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sora_agent_sa.email}"
}

# Artifact Registry Docker Repository
resource "google_artifact_registry_repository" "sora_repo" {
  location      = var.region
  repository_id = "sora-agent-repo"
  description   = "Container registry for Sora Japan Travel Agent images"
  format        = "DOCKER"
  depends_on    = [google_project_service.enabled_apis]
}

# Cloud Run v2 Service with Secret Manager Injection & Health Probes
resource "google_cloud_run_v2_service" "sora_service" {
  name     = var.service_name
  location = var.region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = google_service_account.sora_agent_sa.email

    scaling {
      min_instance_count = var.min_instance_count
      max_instance_count = var.max_instance_count
    }

    containers {
      image = var.container_image

      ports {
        container_port = 8000
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }

      env {
        name  = "GCP_PROJECT_ID"
        value = var.project_id
      }

      env {
        name  = "SORA_GEMINI_SECRET_ID"
        value = google_secret_manager_secret.gemini_api_key.secret_id
      }

      env {
        name  = "SORA_SESSION_DB_PATH"
        value = "/tmp/sora_sessions.db"
      }

      env {
        name = "GEMINI_API_KEY"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.gemini_api_key.secret_id
            version = "latest"
          }
        }
      }

      startup_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        initial_delay_seconds = 3
        period_seconds        = 5
        failure_threshold     = 3
      }

      liveness_probe {
        http_get {
          path = "/api/health"
          port = 8000
        }
        period_seconds = 30
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_iam_member.sora_secret_accessor,
    google_project_iam_member.vertex_ai_user,
  ]
}
