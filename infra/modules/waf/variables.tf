variable "cloudfront_distribution_id" {
  type        = string
  description = "CloudFront distribution ID to associate with WAF"
  default     = ""
}

variable "api_gateway_arn" {
  type        = string
  description = "API Gateway ARN to associate with WAF (optional)"
  default     = ""
}

variable "rate_limit" {
  type        = number
  description = "Rate limit for rate-based rule (requests per 5 minutes)"
  default     = 2000
}

variable "environment" {
  type        = string
  description = "Environment name (dev, staging, prod)"
  default     = "dev"
}

