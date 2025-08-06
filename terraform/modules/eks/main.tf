# EKS Module for AI Teddy Bear
# Production-ready EKS cluster with child safety compliance

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.20"
    }
  }
}

# Local values
locals {
  cluster_name = "${var.name_prefix}-cluster"
}

# EKS Cluster
resource "aws_eks_cluster" "main" {
  name     = local.cluster_name
  role_arn = aws_iam_role.cluster_role.arn
  version  = var.cluster_version

  vpc_config {
    subnet_ids              = var.subnet_ids
    endpoint_private_access = var.cluster_endpoint_private_access
    endpoint_public_access  = var.cluster_endpoint_public_access
    public_access_cidrs    = var.cluster_endpoint_public_access_cidrs
    security_group_ids     = [aws_security_group.cluster.id]
  }

  # Enhanced logging for child safety compliance
  enabled_log_types = var.cluster_enabled_log_types

  # Encryption configuration for COPPA compliance
  dynamic "encryption_config" {
    for_each = var.cluster_encryption_config
    content {
      provider {
        key_arn = encryption_config.value.provider_key_arn
      }
      resources = encryption_config.value.resources
    }
  }

  # Ensure proper IAM permissions are in place
  depends_on = [
    aws_iam_role_policy_attachment.cluster_policy,
    aws_iam_role_policy_attachment.cluster_service_policy,
    aws_cloudwatch_log_group.cluster,
  ]

  tags = merge(var.tags, {
    Name                  = local.cluster_name
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
    COPPACompliant       = "true"
    ChildSafetyValidated = "true"
  })
}

# CloudWatch Log Group for EKS cluster logs
resource "aws_cloudwatch_log_group" "cluster" {
  name              = "/aws/eks/${local.cluster_name}/cluster"
  retention_in_days = var.cluster_log_retention_days
  kms_key_id       = var.cluster_encryption_config[0].provider_key_arn

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-logs"
    COPPACompliant = "true"
  })
}

# EKS Cluster Security Group
resource "aws_security_group" "cluster" {
  name_prefix = "${local.cluster_name}-cluster-"
  vpc_id      = var.vpc_id

  # Allow HTTPS inbound from worker nodes
  ingress {
    description = "HTTPS from worker nodes"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    self        = true
  }

  # Allow all outbound traffic
  egress {
    description = "All outbound traffic"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-cluster-sg"
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
  })

  lifecycle {
    create_before_destroy = true
  }
}

# EKS Cluster IAM Role
resource "aws_iam_role" "cluster_role" {
  name = "${local.cluster_name}-cluster-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "eks.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Attach required policies to cluster role
resource "aws_iam_role_policy_attachment" "cluster_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSClusterPolicy"
  role       = aws_iam_role.cluster_role.name
}

resource "aws_iam_role_policy_attachment" "cluster_service_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSServicePolicy"
  role       = aws_iam_role.cluster_role.name
}

# Enhanced IAM policy for child safety compliance
resource "aws_iam_role_policy" "cluster_child_safety_policy" {
  name = "${local.cluster_name}-child-safety-policy"
  role = aws_iam_role.cluster_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
          "logs:DescribeLogGroups",
          "logs:DescribeLogStreams"
        ]
        Resource = [
          "arn:aws:logs:*:*:log-group:/aws/eks/${local.cluster_name}/*",
          "arn:aws:logs:*:*:log-group:/child-safety/*",
          "arn:aws:logs:*:*:log-group:/coppa-compliance/*"
        ]
      },
      {
        Effect = "Allow"
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey"
        ]
        Resource = var.cluster_encryption_config[0].provider_key_arn
        Condition = {
          StringEquals = {
            "kms:ViaService" = "logs.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

# EKS Node Groups
resource "aws_eks_node_group" "main" {
  for_each = var.node_groups

  cluster_name    = aws_eks_cluster.main.name
  node_group_name = "${local.cluster_name}-${each.key}"
  node_role_arn   = aws_iam_role.node_role.arn
  subnet_ids      = var.subnet_ids

  # Instance configuration
  instance_types = each.value.instance_types
  ami_type       = lookup(each.value, "ami_type", "AL2_x86_64")
  capacity_type  = lookup(each.value, "capacity_type", "ON_DEMAND")
  disk_size      = lookup(each.value, "disk_size", 20)

  # Scaling configuration
  scaling_config {
    desired_size = each.value.desired_capacity
    max_size     = each.value.max_capacity
    min_size     = each.value.min_capacity
  }

  # Update configuration for zero-downtime deployments
  update_config {
    max_unavailable_percentage = 25
  }

  # Remote access configuration (if needed)
  dynamic "remote_access" {
    for_each = lookup(each.value, "enable_remote_access", false) ? [1] : []
    content {
      ec2_ssh_key               = lookup(each.value, "key_name", null)
      source_security_group_ids = lookup(each.value, "source_security_group_ids", null)
    }
  }

  # Kubernetes labels
  labels = merge(
    lookup(each.value, "k8s_labels", {}),
    {
      "node-group"            = each.key
      "coppa-compliant"       = "true"
      "child-safety-validated" = "true"
    }
  )

  # Kubernetes taints
  dynamic "taint" {
    for_each = lookup(each.value, "k8s_taints", [])
    content {
      key    = taint.value.key
      value  = taint.value.value
      effect = taint.value.effect
    }
  }

  # Launch template (if specified)
  dynamic "launch_template" {
    for_each = lookup(each.value, "launch_template", null) != null ? [each.value.launch_template] : []
    content {
      id      = lookup(launch_template.value, "id", null)
      name    = lookup(launch_template.value, "name", null)
      version = lookup(launch_template.value, "version", "$Latest")
    }
  }

  # Ensure proper IAM permissions
  depends_on = [
    aws_iam_role_policy_attachment.node_policy,
    aws_iam_role_policy_attachment.cni_policy,
    aws_iam_role_policy_attachment.registry_policy,
  ]

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-${each.key}-node-group"
    "kubernetes.io/cluster/${local.cluster_name}" = "owned"
    COPPACompliant = "true"
    ChildSafetyValidated = "true"
  })

  lifecycle {
    ignore_changes = [scaling_config[0].desired_size]
  }
}

# EKS Node Group IAM Role
resource "aws_iam_role" "node_role" {
  name = "${local.cluster_name}-node-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = var.tags
}

# Attach required policies to node role
resource "aws_iam_role_policy_attachment" "node_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKSWorkerNodePolicy"
  role       = aws_iam_role.node_role.name
}

resource "aws_iam_role_policy_attachment" "cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.node_role.name
}

resource "aws_iam_role_policy_attachment" "registry_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
  role       = aws_iam_role.node_role.name
}

# Additional IAM policy for child safety compliance monitoring
resource "aws_iam_role_policy" "node_child_safety_policy" {
  name = "${local.cluster_name}-node-child-safety-policy"
  role = aws_iam_role.node_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "cloudwatch:PutMetricData",
          "cloudwatch:GetMetricStatistics",
          "cloudwatch:ListMetrics",
          "logs:PutLogEvents",
          "logs:CreateLogStream",
          "logs:CreateLogGroup"
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [
          "arn:aws:secretsmanager:*:*:secret:ai-teddy-bear/*"
        ]
      }
    ]
  })
}

# OIDC Identity Provider for service accounts
data "tls_certificate" "cluster" {
  url = aws_eks_cluster.main.identity[0].oidc[0].issuer
}

resource "aws_iam_openid_connect_provider" "cluster" {
  client_id_list  = ["sts.amazonaws.com"]
  thumbprint_list = [data.tls_certificate.cluster.certificates[0].sha1_fingerprint]
  url             = aws_eks_cluster.main.identity[0].oidc[0].issuer

  tags = merge(var.tags, {
    Name = "${local.cluster_name}-oidc"
  })
}

# EKS Addons for enhanced functionality
resource "aws_eks_addon" "vpc_cni" {
  cluster_name             = aws_eks_cluster.main.name
  addon_name               = "vpc-cni"
  addon_version            = var.vpc_cni_version
  resolve_conflicts        = "OVERWRITE"
  service_account_role_arn = aws_iam_role.vpc_cni_role.arn

  tags = var.tags
}

resource "aws_eks_addon" "coredns" {
  cluster_name      = aws_eks_cluster.main.name
  addon_name        = "coredns"
  addon_version     = var.coredns_version
  resolve_conflicts = "OVERWRITE"

  tags = var.tags

  depends_on = [aws_eks_node_group.main]
}

resource "aws_eks_addon" "kube_proxy" {
  cluster_name      = aws_eks_cluster.main.name
  addon_name        = "kube-proxy"
  addon_version     = var.kube_proxy_version
  resolve_conflicts = "OVERWRITE"

  tags = var.tags
}

# IAM role for VPC CNI addon
resource "aws_iam_role" "vpc_cni_role" {
  name = "${local.cluster_name}-vpc-cni-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRoleWithWebIdentity"
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.cluster.arn
        }
        Condition = {
          StringEquals = {
            "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:sub" = "system:serviceaccount:kube-system:aws-node"
            "${replace(aws_iam_openid_connect_provider.cluster.url, "https://", "")}:aud" = "sts.amazonaws.com"
          }
        }
      }
    ]
  })

  tags = var.tags
}

resource "aws_iam_role_policy_attachment" "vpc_cni_policy" {
  policy_arn = "arn:aws:iam::aws:policy/AmazonEKS_CNI_Policy"
  role       = aws_iam_role.vpc_cni_role.name
}

# Data sources
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}