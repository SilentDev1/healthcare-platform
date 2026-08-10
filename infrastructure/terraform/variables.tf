variable "project_id" {
  type = string
}

variable "region" {
  type    = string
  default = "us-east4"
}

variable "environment" {
  type    = string
  default = "beta"
}

variable "web_image" {
  type = string
}

variable "api_image" {
  type = string
}

variable "job_image" {
  type = string
}

variable "public_app_url" {
  type = string
}

variable "api_public_url" {
  type = string
}

variable "allowed_origins" {
  type = string
}

variable "trusted_hosts" {
  type = string
}

variable "feedback_email" {
  type    = string
  default = ""
}

variable "seo_indexing_enabled" {
  type    = bool
  default = false
}
