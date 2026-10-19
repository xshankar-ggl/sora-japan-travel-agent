output "cloud_run_service_url" {
  description = "Public HTTPS URL of the deployed Sora Japan Travel Agent Cloud Run service."
  value       = google_cloud_run_v2_service.sora_service.uri
}

output "service_account_email" {
  description = "Runtime service account email used by the Sora Agent."
  value       = google_service_account.sora_agent_sa.email
}

output "secret_manager_resource_name" {
  description = "Google Cloud Secret Manager resource ID for the Gemini API key."
  value       = google_secret_manager_secret.gemini_api_key.name
}

output "artifact_registry_repository" {
  description = "Artifact Registry Docker repository ID."
  value       = google_artifact_registry_repository.sora_repo.name
}
