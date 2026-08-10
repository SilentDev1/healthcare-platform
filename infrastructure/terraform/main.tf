locals {
  prefix = "carevero-${var.environment}"
  labels = {
    app         = "carevero"
    environment = var.environment
    managed_by  = "terraform"
  }
  required_services = toset([
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "cloudscheduler.googleapis.com",
    "iam.googleapis.com",
    "logging.googleapis.com",
    "monitoring.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com",
    "sqladmin.googleapis.com",
    "storage.googleapis.com",
  ])
}

resource "google_project_service" "required" {
  for_each           = local.required_services
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

resource "google_artifact_registry_repository" "containers" {
  depends_on    = [google_project_service.required]
  location      = var.region
  repository_id = "carevero"
  format        = "DOCKER"
  description   = "Carevero private beta containers"
  labels        = local.labels
}

resource "google_service_account" "api" {
  account_id   = "${local.prefix}-api"
  display_name = "Carevero beta API"
}

resource "google_service_account" "web" {
  account_id   = "${local.prefix}-web"
  display_name = "Carevero beta web"
}

resource "google_service_account" "job" {
  account_id   = "${local.prefix}-job"
  display_name = "Carevero beta import job"
}

resource "google_service_account" "scheduler" {
  account_id   = "${local.prefix}-scheduler"
  display_name = "Carevero beta scheduler"
}

resource "google_secret_manager_secret" "database_url" {
  depends_on = [google_project_service.required]
  secret_id  = "${local.prefix}-database-url"
  replication {
    auto {}
  }
  labels = local.labels
}

resource "google_storage_bucket" "sources" {
  name                        = "${local.prefix}-sources-${var.project_id}"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  force_destroy               = false
  versioning {
    enabled = true
  }
  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["tmp/"]
    }
    action {
      type = "Delete"
    }
  }
  labels = local.labels
}

resource "google_sql_database_instance" "postgres" {
  depends_on          = [google_project_service.required]
  name                = "${local.prefix}-postgres"
  database_version    = "POSTGRES_17"
  region              = var.region
  deletion_protection = true

  settings {
    edition           = "ENTERPRISE"
    tier              = "db-custom-1-3840"
    availability_type = "ZONAL"
    disk_type         = "PD_SSD"
    disk_size         = 30
    disk_autoresize   = true
    user_labels       = local.labels

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true
      start_time                     = "07:00"
      backup_retention_settings {
        retained_backups = 7
        retention_unit   = "COUNT"
      }
    }

    ip_configuration {
      ipv4_enabled = true
      ssl_mode     = "ENCRYPTED_ONLY"
    }

    insights_config {
      query_insights_enabled  = true
      query_string_length     = 1024
      record_application_tags = false
      record_client_address   = false
    }
  }
}

resource "google_sql_database" "app" {
  name     = "carevero"
  instance = google_sql_database_instance.postgres.name
}

resource "google_project_iam_member" "api_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.api.email}"
}

resource "google_project_iam_member" "job_cloudsql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.job.email}"
}

resource "google_secret_manager_secret_iam_member" "api_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.api.email}"
}

resource "google_secret_manager_secret_iam_member" "job_database_url" {
  secret_id = google_secret_manager_secret.database_url.id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.job.email}"
}

resource "google_storage_bucket_iam_member" "job_sources" {
  bucket = google_storage_bucket.sources.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.job.email}"
}

resource "google_cloud_run_v2_service" "api" {
  depends_on          = [google_project_service.required]
  name                = "${local.prefix}-api"
  location            = var.region
  deletion_protection = true

  template {
    service_account                  = google_service_account.api.email
    timeout                          = "60s"
    max_instance_request_concurrency = 40

    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }

    volumes {
      name = "cloudsql"
      cloud_sql_instance {
        instances = [google_sql_database_instance.postgres.connection_name]
      }
    }

    containers {
      image = var.api_image
      volume_mounts {
        name       = "cloudsql"
        mount_path = "/cloudsql"
      }
      resources {
        limits   = { cpu = "1", memory = "1Gi" }
        cpu_idle = true
      }
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "APP_VERSION"
        value = "terraform-deploy"
      }
      env {
        name  = "PUBLIC_APP_URL"
        value = var.public_app_url
      }
      env {
        name  = "API_PUBLIC_URL"
        value = var.api_public_url
      }
      env {
        name  = "ALLOWED_ORIGINS"
        value = var.allowed_origins
      }
      env {
        name  = "TRUSTED_HOSTS"
        value = var.trusted_hosts
      }
      env {
        name  = "SOURCE_STORAGE_BUCKET"
        value = google_storage_bucket.sources.name
      }
      env {
        name  = "ADMIN_API_ENABLED"
        value = "false"
      }
      env {
        name  = "PUBLIC_PRICING_ENABLED"
        value = "true"
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.database_url.secret_id
            version = "latest"
          }
        }
      }
      startup_probe {
        http_get { path = "/health" }
        initial_delay_seconds = 2
        timeout_seconds       = 2
        failure_threshold     = 10
      }
      liveness_probe {
        http_get { path = "/health" }
        period_seconds = 30
      }
    }
  }
}

resource "google_cloud_run_v2_service" "web" {
  depends_on          = [google_project_service.required]
  name                = "${local.prefix}-web"
  location            = var.region
  deletion_protection = true

  template {
    service_account                  = google_service_account.web.email
    timeout                          = "60s"
    max_instance_request_concurrency = 60
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = var.web_image
      resources {
        limits   = { cpu = "1", memory = "512Mi" }
        cpu_idle = true
      }
      env {
        name  = "APP_ENV"
        value = var.environment
      }
      env {
        name  = "BETA_MODE"
        value = "true"
      }
      env {
        name  = "PUBLIC_APP_URL"
        value = var.public_app_url
      }
      env {
        name  = "API_PUBLIC_URL"
        value = var.api_public_url
      }
      env {
        name  = "NEXT_PUBLIC_SITE_URL"
        value = var.public_app_url
      }
      env {
        name  = "SEO_INDEXING_ENABLED"
        value = tostring(var.seo_indexing_enabled)
      }
      env {
        name  = "FEEDBACK_ENABLED"
        value = tostring(var.feedback_email != "")
      }
      env {
        name  = "BETA_FEEDBACK_EMAIL"
        value = var.feedback_email
      }
      startup_probe {
        http_get { path = "/" }
        initial_delay_seconds = 2
        timeout_seconds       = 3
        failure_threshold     = 10
      }
    }
  }
}

resource "google_cloud_run_v2_job" "refresh" {
  depends_on          = [google_project_service.required]
  name                = "${local.prefix}-price-refresh"
  location            = var.region
  deletion_protection = true
  template {
    parallelism = 1
    task_count  = 1
    template {
      service_account = google_service_account.job.email
      timeout         = "7200s"
      max_retries     = 1
      volumes {
        name = "cloudsql"
        cloud_sql_instance {
          instances = [google_sql_database_instance.postgres.connection_name]
        }
      }
      volumes {
        name = "sources"
        gcs {
          bucket    = google_storage_bucket.sources.name
          read_only = false
        }
      }
      containers {
        image = var.job_image
        args  = ["--state", "NH", "--mode", "refresh"]
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
        volume_mounts {
          name       = "sources"
          mount_path = "/mnt/sources"
        }
        resources { limits = { cpu = "2", memory = "4Gi" } }
        env {
          name  = "APP_ENV"
          value = var.environment
        }
        env {
          name  = "SCHEDULER_ENABLED"
          value = "true"
        }
        env {
          name  = "SOURCE_STORAGE_BUCKET"
          value = google_storage_bucket.sources.name
        }
        env {
          name  = "HOSPITAL_PRICE_RAW_DIR"
          value = "/mnt/sources/hospital-prices/US/NH"
        }
        env {
          name = "DATABASE_URL"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.database_url.secret_id
              version = "latest"
            }
          }
        }
      }
    }
  }
}

resource "google_cloud_run_v2_service_iam_member" "api_public" {
  location = google_cloud_run_v2_service.api.location
  name     = google_cloud_run_v2_service.api.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "web_public" {
  location = google_cloud_run_v2_service.web.location
  name     = google_cloud_run_v2_service.web.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_project_iam_member" "scheduler_runner" {
  project = var.project_id
  role    = "roles/run.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

resource "google_cloud_scheduler_job" "daily_refresh" {
  depends_on = [google_project_service.required]
  name       = "${local.prefix}-daily-refresh"
  region     = var.region
  schedule   = "17 2 * * *"
  time_zone  = "America/New_York"
  paused     = true
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.refresh.name}:run"
    oauth_token { service_account_email = google_service_account.scheduler.email }
    headers = { "Content-Type" = "application/json" }
    body = base64encode(jsonencode({
      overrides = { containerOverrides = [{ args = ["--state", "NH", "--mode", "refresh"] }] }
    }))
  }
  retry_config {
    retry_count          = 1
    min_backoff_duration = "60s"
    max_backoff_duration = "300s"
  }
}

resource "google_cloud_scheduler_job" "weekly_discovery" {
  depends_on = [google_project_service.required]
  name       = "${local.prefix}-weekly-discovery"
  region     = var.region
  schedule   = "41 3 * * 0"
  time_zone  = "America/New_York"
  paused     = true
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.refresh.name}:run"
    oauth_token { service_account_email = google_service_account.scheduler.email }
    headers = { "Content-Type" = "application/json" }
    body = base64encode(jsonencode({
      overrides = { containerOverrides = [{ args = ["--state", "NH", "--mode", "discover"] }] }
    }))
  }
  retry_config { retry_count = 1 }
}

resource "google_cloud_scheduler_job" "monthly_audit" {
  depends_on = [google_project_service.required]
  name       = "${local.prefix}-monthly-audit"
  region     = var.region
  schedule   = "13 4 1 * *"
  time_zone  = "America/New_York"
  paused     = true
  http_target {
    http_method = "POST"
    uri         = "https://${var.region}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${var.project_id}/jobs/${google_cloud_run_v2_job.refresh.name}:run"
    oauth_token { service_account_email = google_service_account.scheduler.email }
    headers = { "Content-Type" = "application/json" }
    body = base64encode(jsonencode({
      overrides = { containerOverrides = [{ args = ["--state", "NH", "--mode", "audit"] }] }
    }))
  }
  retry_config { retry_count = 1 }
}
