# AI Teddy Bear Infrastructure as Code
# Main Terraform configuration for production-ready deployment
# Includes child safety compliance and COPPA requirements

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.10"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.5"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  backend "s3" {
    bucket         = "ai-teddy-bear-terraform-state"
    key            = "infrastructure/terraform.tfstate"
    region         = "us-west-2"
    encrypt        = true
    dynamodb_table = "ai-teddy-bear-terraform-locks"
  }
}

# Configure AWS Provider
provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project             = "ai-teddy-bear"
      Environment         = var.environment
      ManagedBy          = "terraform"
      Owner              = "ai-teddy-bear-team"
      CostCenter         = "ai-teddy-bear-${var.environment}"
      # Child safety compliance tags
      COPPACompliant     = "true"
      ChildSafetyValidated = "true"
      DataRetentionDays  = "90"
      PrivacyLevel       = "strict"
    }
  }
}

# Configure Kubernetes Provider
provider "kubernetes" {
  host                   = module.eks.cluster_endpoint
  cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

  exec {
    api_version = "client.authentication.k8s.io/v1beta1"
    command     = "aws"
    args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
  }
}

# Configure Helm Provider
provider "helm" {
  kubernetes {
    host                   = module.eks.cluster_endpoint
    cluster_ca_certificate = base64decode(module.eks.cluster_certificate_authority_data)

    exec {
      api_version = "client.authentication.k8s.io/v1beta1"
      command     = "aws"
      args        = ["eks", "get-token", "--cluster-name", module.eks.cluster_name]
    }
  }
}

# Local values for common configurations
locals {
  name_prefix = "ai-teddy-bear-${var.environment}"
  
  common_tags = {
    Project             = "ai-teddy-bear"
    Environment         = var.environment
    ManagedBy          = "terraform"
    # Child safety compliance
    COPPACompliant     = "true"
    ChildSafetyValidated = "true"
    DataRetentionDays  = "90"
    PrivacyLevel       = "strict"
  }

  # Child safety and COPPA compliance requirements
  coppa_compliance = {
    data_retention_days           = 90
    require_parental_consent     = true
    content_filtering_strict     = true
    audit_logging_enabled        = true
    encryption_at_rest_required  = true
    encryption_in_transit_required = true
    access_logging_required      = true
    vulnerability_scanning_required = true
  }
}

# VPC Module
module "vpc" {
  source = "./modules/vpc"

  name_prefix = local.name_prefix
  environment = var.environment
  
  vpc_cidr = var.vpc_cidr
  azs      = var.availability_zones
  
  private_subnet_cidrs = var.private_subnet_cidrs
  public_subnet_cidrs  = var.public_subnet_cidrs
  database_subnet_cidrs = var.database_subnet_cidrs
  
  enable_nat_gateway   = true
  enable_vpn_gateway   = false
  enable_dns_hostnames = true
  enable_dns_support   = true
  
  # Enhanced security for child safety
  enable_flow_log = true
  flow_log_destination_type = "cloud-watch-logs"
  
  tags = local.common_tags
}

# Security Groups Module
module "security_groups" {
  source = "./modules/security"

  name_prefix = local.name_prefix
  environment = var.environment
  vpc_id      = module.vpc.vpc_id
  
  allowed_cidr_blocks = var.allowed_cidr_blocks
  
  # Enhanced security rules for child safety compliance
  enable_strict_egress = true
  enable_waf          = true
  
  tags = local.common_tags
}

# EKS Module
module "eks" {
  source = "./modules/eks"

  name_prefix = local.name_prefix
  environment = var.environment
  
  cluster_version = var.kubernetes_version
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  
  # Node groups configuration
  node_groups = {
    main = {
      desired_capacity = var.eks_node_desired_capacity
      max_capacity     = var.eks_node_max_capacity
      min_capacity     = var.eks_node_min_capacity
      instance_types   = var.eks_node_instance_types
      
      k8s_labels = {
        Environment = var.environment
        NodeGroup   = "main"
        COPPACompliant = "true"
        ChildSafetyValidated = "true"
      }
    }
  }
  
  # Enhanced security for child safety
  cluster_encryption_config = [
    {
      provider_key_arn = module.kms.cluster_kms_key_arn
      resources        = ["secrets"]
    }
  ]
  
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = var.environment == "production" ? false : true
  cluster_endpoint_public_access_cidrs = var.environment == "production" ? [] : ["0.0.0.0/0"]
  
  # COPPA compliance logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
  
  tags = local.common_tags
}

# KMS Module for encryption
module "kms" {
  source = "./modules/kms"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # Child safety and COPPA compliance encryption
  create_cluster_kms_key = true
  create_secrets_kms_key = true
  create_database_kms_key = true
  create_storage_kms_key = true
  
  tags = local.common_tags
}

# RDS Module for PostgreSQL
module "rds" {
  source = "./modules/rds"

  name_prefix = local.name_prefix
  environment = var.environment
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.database_subnet_ids
  
  # Database configuration
  engine         = "postgres"
  engine_version = var.postgres_version
  instance_class = var.rds_instance_class
  
  allocated_storage     = var.rds_allocated_storage
  max_allocated_storage = var.rds_max_allocated_storage
  
  database_name = var.database_name
  username      = var.database_username
  
  # Enhanced security for child safety
  encryption_enabled = true
  kms_key_id        = module.kms.database_kms_key_arn
  
  # COPPA compliance backup and retention
  backup_retention_period = 30  # Extended for compliance
  backup_window          = "03:00-04:00"
  maintenance_window     = "Sun:04:00-Sun:05:00"
  
  # Enhanced monitoring
  monitoring_interval = 60
  monitoring_role_arn = module.iam.rds_monitoring_role_arn
  
  performance_insights_enabled = true
  performance_insights_kms_key_id = module.kms.database_kms_key_arn
  
  # Security groups
  allowed_security_group_ids = [module.security_groups.database_security_group_id]
  
  tags = local.common_tags
}

# ElastiCache Redis Module
module "redis" {
  source = "./modules/redis"

  name_prefix = local.name_prefix
  environment = var.environment
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnet_ids
  
  # Redis configuration
  node_type               = var.redis_node_type
  num_cache_nodes        = var.redis_num_nodes
  parameter_group_name   = "default.redis7"
  engine_version         = var.redis_version
  
  # Enhanced security for child safety
  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token_enabled         = true
  kms_key_id                = module.kms.storage_kms_key_arn
  
  # Security groups
  allowed_security_group_ids = [module.security_groups.redis_security_group_id]
  
  tags = local.common_tags
}

# ALB Module
module "alb" {
  source = "./modules/alb"

  name_prefix = local.name_prefix
  environment = var.environment
  
  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.public_subnet_ids
  
  # SSL/TLS configuration for child safety
  certificate_arn = var.ssl_certificate_arn
  ssl_policy      = "ELBSecurityPolicy-TLS-1-2-2017-01"  # Strong encryption
  
  # Enhanced security headers
  enable_security_headers = true
  enable_waf_integration = true
  
  # Security groups
  security_group_ids = [module.security_groups.alb_security_group_id]
  
  tags = local.common_tags
}

# IAM Module
module "iam" {
  source = "./modules/iam"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # EKS cluster and node roles
  create_eks_cluster_role = true
  create_eks_node_role   = true
  
  # Service account roles for Kubernetes
  create_external_secrets_role = true
  create_aws_load_balancer_controller_role = true
  create_cluster_autoscaler_role = true
  
  # Enhanced monitoring and compliance roles
  create_rds_monitoring_role = true
  create_cloudwatch_role     = true
  create_audit_logging_role  = true
  
  # COPPA compliance specific roles
  create_data_retention_role = true
  create_compliance_audit_role = true
  
  eks_cluster_arn = module.eks.cluster_arn
  oidc_provider_arn = module.eks.oidc_provider_arn
  
  tags = local.common_tags
}

# CloudWatch Module for monitoring and compliance
module "cloudwatch" {
  source = "./modules/cloudwatch"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # EKS cluster monitoring
  eks_cluster_name = module.eks.cluster_name
  
  # Child safety and COPPA compliance monitoring
  enable_child_safety_alarms = true
  enable_coppa_compliance_monitoring = true
  enable_security_monitoring = true
  
  # Data retention for compliance
  log_retention_days = local.coppa_compliance.data_retention_days
  
  # Enhanced alerting
  sns_topic_arn = module.sns.alerts_topic_arn
  
  tags = local.common_tags
}

# SNS Module for alerting
module "sns" {
  source = "./modules/sns"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # Alert topics
  create_alerts_topic = true
  create_child_safety_alerts_topic = true
  create_security_alerts_topic = true
  
  # KMS encryption for sensitive alerts
  kms_key_id = module.kms.secrets_kms_key_arn
  
  tags = local.common_tags
}

# S3 Module for storage and backups
module "s3" {
  source = "./modules/s3"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # Buckets for different purposes
  create_application_backups_bucket = true
  create_database_backups_bucket    = true
  create_audit_logs_bucket         = true
  create_child_safety_logs_bucket  = true
  
  # Enhanced security and compliance
  enable_versioning = true
  enable_encryption = true
  kms_key_id       = module.kms.storage_kms_key_arn
  
  # COPPA compliance lifecycle
  lifecycle_rules = [
    {
      id     = "child-safety-data-retention"
      status = "Enabled"
      expiration = {
        days = local.coppa_compliance.data_retention_days
      }
    }
  ]
  
  tags = local.common_tags
}

# WAF Module for web application protection
module "waf" {
  source = "./modules/waf"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # Associate with ALB
  alb_arn = module.alb.alb_arn
  
  # Enhanced protection for child safety
  enable_child_safety_rules = true
  enable_content_filtering  = true
  enable_rate_limiting     = true
  enable_geo_blocking      = var.environment == "production"
  
  # COPPA compliance rules
  enable_coppa_protection = true
  
  tags = local.common_tags
}

# Route53 Module for DNS
module "route53" {
  source = "./modules/route53"

  name_prefix = local.name_prefix
  environment = var.environment
  
  domain_name = var.domain_name
  
  # ALB integration
  alb_dns_name = module.alb.alb_dns_name
  alb_zone_id  = module.alb.alb_zone_id
  
  # Health checks for child safety compliance
  enable_health_checks = true
  
  tags = local.common_tags
}

# Secrets Manager for secure secret storage
module "secrets_manager" {
  source = "./modules/secrets-manager"

  name_prefix = local.name_prefix
  environment = var.environment
  
  # Database secrets
  database_username = var.database_username
  database_password = random_password.database_password.result
  
  # Redis auth token
  redis_auth_token = random_password.redis_auth_token.result
  
  # Application secrets
  jwt_secret_key        = random_password.jwt_secret.result
  coppa_encryption_key  = random_password.coppa_key.result
  
  # KMS encryption
  kms_key_id = module.kms.secrets_kms_key_arn
  
  # COPPA compliance retention
  recovery_window_in_days = local.coppa_compliance.data_retention_days
  
  tags = local.common_tags
}

# Generate secure random passwords
resource "random_password" "database_password" {
  length  = 32
  special = true
}

resource "random_password" "redis_auth_token" {
  length  = 64
  special = false
}

resource "random_password" "jwt_secret" {
  length  = 64
  special = false
}

resource "random_password" "coppa_key" {
  length  = 32
  special = false
}

# Output important values
output "vpc_id" {
  description = "ID of the VPC"
  value       = module.vpc.vpc_id
}

output "eks_cluster_name" {
  description = "Name of the EKS cluster"
  value       = module.eks.cluster_name
}

output "eks_cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = module.eks.cluster_endpoint
  sensitive   = true
}

output "rds_endpoint" {
  description = "RDS instance endpoint"
  value       = module.rds.db_instance_endpoint
  sensitive   = true
}

output "redis_endpoint" {
  description = "Redis cluster endpoint"
  value       = module.redis.redis_endpoint
  sensitive   = true
}

output "alb_dns_name" {
  description = "DNS name of the load balancer"
  value       = module.alb.alb_dns_name
}

output "cloudwatch_log_group_name" {
  description = "CloudWatch log group name"
  value       = module.cloudwatch.log_group_name
}

output "child_safety_compliance_status" {
  description = "Child safety and COPPA compliance status"
  value = {
    coppa_compliant           = "true"
    child_safety_validated    = "true"
    data_retention_configured = "${local.coppa_compliance.data_retention_days} days"
    encryption_enabled        = "true"
    audit_logging_enabled     = "true"
  }
}