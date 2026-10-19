variable "project_id" {
  description = "Google Cloud Project ID hosting the Sora Japan Travel Agent."
  type        = string
}

variable "region" {
  description = "Primary GCP region for Cloud Run, Artifact Registry, and Vertex AI."
  type        = string
  default     = "us-central1"
}

variable "service_name" {
  description = "Name of the Cloud Run v2 service."
  type        = string
  default     = "sora-japan-travel-agent"
}

variable "container_image" {
  description = "Container image URI in Artifact Registry to deploy to Cloud Run."
  type        = string
  default     = "us-central1-docker.pkg.dev/sora-project/sora-repo/sora-japan-travel-agent:latest"
}

variable "gemini_secret_id" {
  description = "Secret Manager secret ID storing the Gemini API key."
  type        = string
  default     = "sora-gemini-api-key"
}

variable "min_instance_count" {
  description = "Minimum warm Cloud Run instances."
  type        = number
  default     = 0
}

variable "max_instance_count" {
  description = "Maximum autoscaled Cloud Run instances."
  type        = number
  default     = 10
}
