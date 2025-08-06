# EKS Module Variables

variable "name_prefix" {
  description = "Prefix for resource names"
  type        = string
}

variable "environment" {
  description = "Environment name"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID where EKS cluster will be created"
  type        = string
}

variable "subnet_ids" {
  description = "List of subnet IDs for EKS cluster"
  type        = list(string)
}

variable "cluster_version" {
  description = "Kubernetes version for EKS cluster"
  type        = string
  default     = "1.28"
}

variable "cluster_endpoint_private_access" {
  description = "Enable private API server endpoint"
  type        = bool
  default     = true
}

variable "cluster_endpoint_public_access" {
  description = "Enable public API server endpoint"
  type        = bool
  default     = false
}

variable "cluster_endpoint_public_access_cidrs" {
  description = "List of CIDR blocks that can access the public API server endpoint"
  type        = list(string)
  default     = []
}

variable "cluster_enabled_log_types" {
  description = "List of log types to enable for EKS cluster"
  type        = list(string)
  default     = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "cluster_log_retention_days" {
  description = "Number of days to retain cluster logs"
  type        = number
  default     = 90
}

variable "cluster_encryption_config" {
  description = "Configuration block with encryption configuration for the cluster"
  type = list(object({
    provider_key_arn = string
    resources        = list(string)
  }))
  default = []
}

variable "node_groups" {
  description = "Map of EKS node group configurations"
  type = map(object({
    desired_capacity = number
    max_capacity     = number
    min_capacity     = number
    instance_types   = list(string)
    ami_type         = optional(string, "AL2_x86_64")
    capacity_type    = optional(string, "ON_DEMAND")
    disk_size        = optional(number, 20)
    k8s_labels       = optional(map(string), {})
    k8s_taints       = optional(list(object({
      key    = string
      value  = string
      effect = string
    })), [])
    enable_remote_access = optional(bool, false)
    key_name            = optional(string, null)
    source_security_group_ids = optional(list(string), null)
    launch_template     = optional(object({
      id      = optional(string, null)
      name    = optional(string, null)
      version = optional(string, "$Latest")
    }), null)
  }))
  default = {}
}

variable "vpc_cni_version" {
  description = "Version of VPC CNI addon"
  type        = string
  default     = null
}

variable "coredns_version" {
  description = "Version of CoreDNS addon"
  type        = string
  default     = null
}

variable "kube_proxy_version" {
  description = "Version of kube-proxy addon"
  type        = string
  default     = null
}

variable "enable_irsa" {
  description = "Enable IAM Roles for Service Accounts"
  type        = bool
  default     = true
}

variable "tags" {
  description = "A map of tags to assign to resources"
  type        = map(string)
  default     = {}
}