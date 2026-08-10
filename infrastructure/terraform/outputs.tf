output "web_service_name" { value = google_cloud_run_v2_service.web.name }
output "api_service_name" { value = google_cloud_run_v2_service.api.name }
output "refresh_job_name" { value = google_cloud_run_v2_job.refresh.name }
output "source_bucket_name" { value = google_storage_bucket.sources.name }
output "cloud_sql_connection_name" { value = google_sql_database_instance.postgres.connection_name }
