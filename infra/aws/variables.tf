variable "deployment_authorized" {
  type        = bool
  default     = false
  description = "Explicit approval of the proposed account, resources, region and costs. Keep false until approved."
}
variable "aws_account_id" {
  type        = string
  description = "Future target account ID. Never put credentials in Terraform variables."
  validation {
    condition     = can(regex("^[0-9]{12}$", var.aws_account_id))
    error_message = "Provide a 12-digit AWS account ID."
  }
}
variable "region" {
  type    = string
  default = "eu-west-2"
}
variable "name" {
  type    = string
  default = "transit-reliability"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,39}$", var.name))
    error_message = "Use 3-40 lowercase letters, digits and hyphens."
  }
}
variable "bucket_name" {
  type        = string
  description = "Globally unique private bucket name."
  validation {
    condition     = can(regex("^[a-z0-9][a-z0-9-]{1,61}[a-z0-9]$", var.bucket_name))
    error_message = "Use a 3-63 character lowercase bucket name without dots."
  }
}
variable "schedule_enabled" {
  type    = bool
  default = false
}
variable "schedule_expression" {
  type    = string
  default = "rate(1 hour)"
  validation {
    condition     = var.schedule_expression == "rate(1 hour)"
    error_message = "This reviewed cost model supports hourly ingestion only."
  }
}
variable "use_api_secret" {
  type        = bool
  default     = false
  description = "Create an empty secret; populate out of band before enabling scheduling."
}
variable "raw_retention_days" {
  type    = number
  default = 90
  validation {
    condition     = var.raw_retention_days >= 1 && floor(var.raw_retention_days) == var.raw_retention_days
    error_message = "Retention must be a positive integer number of days."
  }
}
