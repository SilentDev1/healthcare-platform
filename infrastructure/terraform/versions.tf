terraform {
  required_version = ">= 1.8.0"
  backend "gcs" {
    bucket = "carevero-beta-tfstate-carecompare-development"
    prefix = "terraform/beta"
  }
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
