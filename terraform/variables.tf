# AI Teddy Bear Infrastructure Variables
# Configuration variables for production-ready deployment

# General Configuration
variable "environment" {
  description = "Environment name (staging, production)"
  type        = string
  validation {
    condition     = contains(["staging", "production"], var.environment)
    error_message = "Environment must be either 'staging' or 'production'."
  }
}

variable "aws_region" {
  description = "AWS region for resources"
  type        = string
  default     = "us-west-2"
}

variable "project_name" {
  description = "Project name for resource naming"
  type        = string
  default     = "ai-teddy-bear"
}

# Network Configuration
variable "vpc_cidr" {
  description = "CIDR block for VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "availability_zones" {
  description = "List of availability zones"
  type        = list(string)
  default     = ["us-west-2a", "us-west-2b", "us-west-2c"]
}

variable "private_subnet_cidrs" {
  description = "CIDR blocks for private subnets"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24", "10.0.3.0/24"]
}

variable "public_subnet_cidrs" {
  description = "CIDR blocks for public subnets"
  type        = list(string)
  default     = ["10.0.101.0/24", "10.0.102.0/24", "10.0.103.0/24"]
}

variable "database_subnet_cidrs" {
  description = "CIDR blocks for database subnets"
  type        = list(string)
  default     = ["10.0.201.0/24", "10.0.202.0/24", "10.0.203.0/24"]
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to access resources"
  type        = list(string)
  default     = ["0.0.0.0/0"]  # Restrict this in production
}

# EKS Configuration
variable "kubernetes_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "eks_node_desired_capacity" {
  description = "Desired number of EKS worker nodes"
  type        = number
  default     = 3
}

variable "eks_node_min_capacity" {
  description = "Minimum number of EKS worker nodes"
  type        = number
  default     = 2
}

variable "eks_node_max_capacity" {
  description = "Maximum number of EKS worker nodes"
  type        = number
  default     = 10
}

variable "eks_node_instance_types" {
  description = "EC2 instance types for EKS worker nodes"
  type        = list(string)
  default     = ["t3.medium", "t3.large"]
}

# Database Configuration
variable "postgres_version" {
  description = "PostgreSQL version"
  type        = string
  default     = "15.4"
}

variable "rds_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t3.micro"
}

variable "rds_allocated_storage" {
  description = "Allocated storage for RDS instance (GB)"
  type        = number
  default     = 20
}

variable "rds_max_allocated_storage" {
  description = "Maximum allocated storage for RDS instance (GB)"
  type        = number
  default     = 100
}

variable "database_name" {
  description = "Name of the database to create"
  type        = string
  default     = "ai_teddy_bear"
}

variable "database_username" {
  description = "Username for the database"
  type        = string
  default     = "ai_teddy_user"
}

# Redis Configuration
variable "redis_version" {
  description = "Redis version"
  type        = string
  default     = "7.0"
}

variable "redis_node_type" {
  description = "Redis node type"
  type        = string
  default     = "cache.t3.micro"
}

variable "redis_num_nodes" {
  description = "Number of Redis nodes"
  type        = number
  default     = 1
}

# SSL/TLS Configuration
variable "ssl_certificate_arn" {
  description = "ARN of SSL certificate for ALB"
  type        = string
  default     = ""
}

variable "domain_name" {
  description = "Domain name for the application"
  type        = string
  default     = "aiteddybear.com"
}

# Child Safety and COPPA Compliance Configuration
variable "enable_coppa_compliance" {
  description = "Enable COPPA compliance features"
  type        = bool
  default     = true
}

variable "enable_child_safety_monitoring" {
  description = "Enable child safety monitoring features"
  type        = bool
  default     = true
}

variable "data_retention_days" {
  description = "Data retention period in days for COPPA compliance"
  type        = number
  default     = 90
  validation {
    condition     = var.data_retention_days >= 30 && var.data_retention_days <= 365
    error_message = "Data retention days must be between 30 and 365."
  }
}

variable "enable_strict_content_filtering" {
  description = "Enable strict content filtering for child safety"
  type        = bool
  default     = true
}

variable "enable_audit_logging" {
  description = "Enable comprehensive audit logging"
  type        = bool
  default     = true
}

variable "enable_encryption_at_rest" {
  description = "Enable encryption at rest for all data stores"
  type        = bool
  default     = true
}

variable "enable_encryption_in_transit" {
  description = "Enable encryption in transit for all communications"
  type        = bool
  default     = true
}

# Security Configuration
variable "enable_waf" {
  description = "Enable AWS WAF for web application protection"
  type        = bool
  default     = true
}

variable "enable_security_monitoring" {
  description = "Enable security monitoring and alerting"
  type        = bool
  default     = true
}

variable "enable_vulnerability_scanning" {
  description = "Enable vulnerability scanning"
  type        = bool
  default     = true
}

variable "allowed_countries" {
  description = "List of allowed countries for geo-blocking (ISO 3166-1 alpha-2)"
  type        = list(string)
  default     = ["US", "CA", "GB", "AU"]  # Adjust based on target markets
}

# Monitoring Configuration
variable "enable_detailed_monitoring" {
  description = "Enable detailed CloudWatch monitoring"
  type        = bool
  default     = true
}

variable "alert_email_addresses" {
  description = "Email addresses for alerts"
  type        = list(string)
  default     = []
}

variable "enable_performance_insights" {
  description = "Enable RDS Performance Insights"
  type        = bool
  default     = true
}

# Backup Configuration
variable "backup_retention_period" {
  description = "Backup retention period in days"
  type        = number
  default     = 30
}

variable "enable_cross_region_backup" {
  description = "Enable cross-region backup for disaster recovery"
  type        = bool
  default     = false  # Enable for production
}

variable "backup_window" {
  description = "Preferred backup window"
  type        = string
  default     = "03:00-04:00"
}

variable "maintenance_window" {
  description = "Preferred maintenance window"
  type        = string
  default     = "Sun:04:00-Sun:05:00"
}

# Cost Optimization
variable "enable_cost_optimization" {
  description = "Enable cost optimization features"
  type        = bool
  default     = true
}

variable "enable_spot_instances" {
  description = "Enable spot instances for non-critical workloads"
  type        = bool
  default     = false  # Disable for production for stability
}

# Feature Flags
variable "enable_blue_green_deployment" {
  description = "Enable blue-green deployment infrastructure"
  type        = bool
  default     = true
}

variable "enable_canary_deployment" {
  description = "Enable canary deployment infrastructure"
  type        = bool
  default     = true
}

variable "enable_auto_scaling" {
  description = "Enable auto-scaling for EKS nodes"
  type        = bool
  default     = true
}

variable "enable_container_insights" {
  description = "Enable Container Insights for EKS"
  type        = bool
  default     = true
}

# External Services Configuration
variable "sentry_dsn" {
  description = "Sentry DSN for error tracking"
  type        = string
  default     = ""
  sensitive   = true
}

variable "openai_api_key" {
  description = "OpenAI API key"
  type        = string
  default     = ""
  sensitive   = true
}

variable "elevenlabs_api_key" {
  description = "ElevenLabs API key"
  type        = string
  default     = ""
  sensitive   = true
}

# Environment-specific overrides
variable "environment_config" {
  description = "Environment-specific configuration overrides"
  type        = map(any)
  default     = {}
}

# Child Safety Compliance Tags
variable "compliance_tags" {
  description = "Additional tags for compliance tracking"
  type        = map(string)
  default = {
    COPPACompliant       = "true"
    ChildSafetyValidated = "true"
    DataClassification   = "sensitive"
    PrivacyLevel         = "strict"
    AuditRequired        = "true"
  }
}

# Resource Naming
variable "resource_prefix" {
  description = "Prefix for resource names"
  type        = string
  default     = ""
}

variable "resource_suffix" {
  description = "Suffix for resource names"
  type        = string
  default     = ""
}

# High Availability Configuration
variable "enable_multi_az" {
  description = "Enable Multi-AZ deployment for high availability"
  type        = bool
  default     = true
}

variable "enable_cross_zone_load_balancing" {
  description = "Enable cross-zone load balancing"
  type        = bool
  default     = true
}

# Disaster Recovery Configuration
variable "enable_disaster_recovery" {
  description = "Enable disaster recovery setup"
  type        = bool
  default     = false  # Enable for production
}

variable "dr_region" {
  description = "Disaster recovery region"
  type        = string
  default     = "us-east-1"
}

# Local values for computed configurations
locals {
  name_prefix = var.resource_prefix != "" ? "${var.resource_prefix}-${var.project_name}" : var.project_name
  name_suffix = var.resource_suffix != "" ? "-${var.resource_suffix}" : ""
  
  environment_defaults = {
    staging = {
      eks_node_desired_capacity = 2
      eks_node_min_capacity     = 1
      eks_node_max_capacity     = 5
      rds_instance_class        = "db.t3.micro"
      redis_node_type          = "cache.t3.micro"
      enable_multi_az          = false
      backup_retention_period  = 7
    }
    production = {
      eks_node_desired_capacity = 3
      eks_node_min_capacity     = 2
      eks_node_max_capacity     = 20
      rds_instance_class        = "db.r6g.large"
      redis_node_type          = "cache.r6g.large"
      enable_multi_az          = true
      backup_retention_period  = 30
    }
  }
  
  # Merge environment-specific defaults with user-provided config
  merged_config = merge(
    local.environment_defaults[var.environment],
    var.environment_config
  )
}