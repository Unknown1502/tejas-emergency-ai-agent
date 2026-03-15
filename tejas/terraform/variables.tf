# ==========================================================================
# Tejas -- Terraform Variables
# ==========================================================================

variable "project_id" {
  description = "Google Cloud project ID"
  type        = string
}

variable "region" {
  description = "Google Cloud region for resource deployment"
  type        = string
  default     = "us-central1"
}

variable "firestore_location" {
  description = "Firestore database location (multi-region or single region)"
  type        = string
  default     = "nam5"
}

variable "environment" {
  description = "Deployment environment (development, staging, production)"
  type        = string
  default     = "production"

  validation {
    condition     = contains(["development", "staging", "production"], var.environment)
    error_message = "Environment must be development, staging, or production."
  }
}

variable "min_instances" {
  description = "Minimum number of Cloud Run instances (0 = scale to zero, 1 = no cold starts)"
  type        = number
  default     = 0
}

variable "max_instances" {
  description = "Maximum number of Cloud Run instances"
  type        = number
  default     = 10
}

variable "cpu_limit" {
  description = "CPU limit per Cloud Run instance"
  type        = string
  default     = "2"
}

variable "memory_limit" {
  description = "Memory limit per Cloud Run instance"
  type        = string
  default     = "1Gi"
}

variable "frontend_url" {
  description = <<-EOT
    HTTPS URL of the deployed frontend Cloud Run service. Used to set
    ALLOWED_ORIGINS on the backend so the browser's CORS preflight passes.

    Leave empty on initial apply. After the frontend service is deployed,
    retrieve its URL and re-apply:
      terraform output frontend_url
      terraform apply -var="frontend_url=https://tejas-frontend-HASH-uc.a.run.app"
  EOT
  type        = string
  default     = ""
}
