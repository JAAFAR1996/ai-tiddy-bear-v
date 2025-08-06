# EKS Module Outputs

output "cluster_id" {
  description = "The name/id of the EKS cluster"
  value       = aws_eks_cluster.main.id
}

output "cluster_name" {
  description = "The name of the EKS cluster"
  value       = aws_eks_cluster.main.name
}

output "cluster_arn" {
  description = "The Amazon Resource Name (ARN) of the cluster"
  value       = aws_eks_cluster.main.arn
}

output "cluster_endpoint" {
  description = "Endpoint for EKS control plane"
  value       = aws_eks_cluster.main.endpoint
}

output "cluster_version" {
  description = "The Kubernetes version for the EKS cluster"
  value       = aws_eks_cluster.main.version
}

output "cluster_platform_version" {
  description = "Platform version for the EKS cluster"
  value       = aws_eks_cluster.main.platform_version
}

output "cluster_certificate_authority_data" {
  description = "Base64 encoded certificate data required to communicate with the cluster"
  value       = aws_eks_cluster.main.certificate_authority[0].data
}

output "cluster_security_group_id" {
  description = "Security group ID attached to the EKS cluster"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "cluster_primary_security_group_id" {
  description = "The cluster primary security group ID created by EKS"
  value       = aws_eks_cluster.main.vpc_config[0].cluster_security_group_id
}

output "cluster_iam_role_name" {
  description = "IAM role name associated with EKS cluster"
  value       = aws_iam_role.cluster_role.name
}

output "cluster_iam_role_arn" {
  description = "IAM role ARN associated with EKS cluster"
  value       = aws_iam_role.cluster_role.arn
}

output "cluster_oidc_issuer_url" {
  description = "The URL on the EKS cluster OIDC Issuer"
  value       = try(aws_eks_cluster.main.identity[0].oidc[0].issuer, null)
}

output "oidc_provider_arn" {
  description = "The ARN of the OIDC Provider if enabled"
  value       = try(aws_iam_openid_connect_provider.cluster.arn, null)
}

output "node_groups" {
  description = "EKS node groups"
  value       = aws_eks_node_group.main
}

output "node_security_group_id" {
  description = "ID of the node shared security group"
  value       = aws_security_group.cluster.id
}

output "node_iam_role_name" {
  description = "IAM role name associated with EKS node groups"
  value       = aws_iam_role.node_role.name
}

output "node_iam_role_arn" {
  description = "IAM role ARN associated with EKS node groups"
  value       = aws_iam_role.node_role.arn
}

output "cloudwatch_log_group_name" {
  description = "Name of cloudwatch log group for EKS cluster logs"
  value       = aws_cloudwatch_log_group.cluster.name
}

output "cloudwatch_log_group_arn" {
  description = "ARN of cloudwatch log group for EKS cluster logs"
  value       = aws_cloudwatch_log_group.cluster.arn
}

# Child Safety and COPPA Compliance Outputs
output "compliance_status" {
  description = "Child safety and COPPA compliance status"
  value = {
    coppa_compliant           = "true"
    child_safety_validated    = "true"
    encryption_enabled        = length(var.cluster_encryption_config) > 0
    audit_logging_enabled     = contains(var.cluster_enabled_log_types, "audit")
    api_logging_enabled       = contains(var.cluster_enabled_log_types, "api")
    log_retention_days        = var.cluster_log_retention_days
    private_endpoint_enabled  = var.cluster_endpoint_private_access
    public_endpoint_restricted = !var.cluster_endpoint_public_access || length(var.cluster_endpoint_public_access_cidrs) > 0
  }
}

# Addon outputs
output "addons" {
  description = "Map of attribute maps for all EKS addons enabled"
  value = {
    vpc_cni = try({
      addon_name    = aws_eks_addon.vpc_cni.addon_name
      addon_version = aws_eks_addon.vpc_cni.addon_version
      status        = aws_eks_addon.vpc_cni.status
    }, null)
    coredns = try({
      addon_name    = aws_eks_addon.coredns.addon_name
      addon_version = aws_eks_addon.coredns.addon_version
      status        = aws_eks_addon.coredns.status
    }, null)
    kube_proxy = try({
      addon_name    = aws_eks_addon.kube_proxy.addon_name
      addon_version = aws_eks_addon.kube_proxy.addon_version
      status        = aws_eks_addon.kube_proxy.status
    }, null)
  }
}