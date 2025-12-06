# Scenario 3: Full Production Stack
# HA Control Plane + Auto-scaling Workers + GPU Nodes
# Cost: ~$500-1000/month

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "IntuitiveOS"
      Environment = "scenario-3"
      Scenario    = "production"
    }
  }
}

variable "aws_region" {
  default = "us-east-1"
}

variable "key_name" {
  description = "SSH key pair name"
  type        = string
  default     = ""
}

variable "enable_gpu" {
  description = "Enable GPU worker nodes"
  type        = bool
  default     = true
}

# VPC with 3 AZs for HA
module "vpc" {
  source = "../../modules/vpc"

  name               = "intuitive-os-prod"
  vpc_cidr           = "10.2.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b", "us-east-1c"]
  enable_nat_gateway = true
}

# Security
module "security" {
  source = "../../modules/security"

  name     = "intuitive-os-prod"
  vpc_id   = module.vpc.vpc_id
  vpc_cidr = module.vpc.vpc_cidr
}

# HA Control Plane + Workers + GPU
module "compute" {
  source = "../../modules/compute"

  name                        = "intuitive-os-prod"
  control_plane_count         = 2  # HA pair
  worker_count                = 3
  gpu_worker_count            = var.enable_gpu ? 2 : 0
  control_plane_instance_type = "t3.large"
  worker_instance_type        = "t3.medium"
  gpu_instance_type           = "g4dn.xlarge"
  subnet_ids                  = module.vpc.private_subnet_ids
  control_plane_sg_id         = module.security.control_plane_sg_id
  worker_sg_id                = module.security.worker_sg_id
  instance_profile            = module.security.node_instance_profile
  key_name                    = var.key_name
}

# Network Load Balancer for K8s API (HA)
resource "aws_lb" "k8s_api" {
  name               = "intuitive-os-prod-nlb"
  internal           = true
  load_balancer_type = "network"
  subnets            = module.vpc.private_subnet_ids

  tags = {
    Name = "intuitive-os-prod-k8s-api"
  }
}

resource "aws_lb_target_group" "k8s_api" {
  name     = "intuitive-os-prod-k8s-api"
  port     = 6443
  protocol = "TCP"
  vpc_id   = module.vpc.vpc_id

  health_check {
    protocol            = "TCP"
    healthy_threshold   = 2
    unhealthy_threshold = 2
  }
}

resource "aws_lb_listener" "k8s_api" {
  load_balancer_arn = aws_lb.k8s_api.arn
  port              = 6443
  protocol          = "TCP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.k8s_api.arn
  }
}

resource "aws_lb_target_group_attachment" "k8s_api" {
  count            = length(module.compute.control_plane_ids)
  target_group_arn = aws_lb_target_group.k8s_api.arn
  target_id        = module.compute.control_plane_ids[count.index]
  port             = 6443
}

# Application Load Balancer for services
resource "aws_lb" "services" {
  name               = "intuitive-os-prod-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.security.lb_sg_id]
  subnets            = module.vpc.public_subnet_ids

  tags = {
    Name = "intuitive-os-prod-services"
  }
}

# EFS for shared storage
resource "aws_efs_file_system" "shared" {
  creation_token = "intuitive-os-prod-efs"
  encrypted      = true

  lifecycle_policy {
    transition_to_ia = "AFTER_30_DAYS"
  }

  tags = {
    Name = "intuitive-os-prod-shared"
  }
}

resource "aws_efs_mount_target" "shared" {
  count           = length(module.vpc.private_subnet_ids)
  file_system_id  = aws_efs_file_system.shared.id
  subnet_id       = module.vpc.private_subnet_ids[count.index]
  security_groups = [module.security.worker_sg_id]
}

# S3 bucket for backups and models
resource "aws_s3_bucket" "data" {
  bucket = "intuitive-os-prod-data-${data.aws_caller_identity.current.account_id}"

  tags = {
    Name = "intuitive-os-prod-data"
  }
}

resource "aws_s3_bucket_versioning" "data" {
  bucket = aws_s3_bucket.data.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "data" {
  bucket = aws_s3_bucket.data.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

data "aws_caller_identity" "current" {}

# Outputs
output "k8s_api_endpoint" {
  value = aws_lb.k8s_api.dns_name
}

output "services_endpoint" {
  value = aws_lb.services.dns_name
}

output "control_plane_ips" {
  value = module.compute.control_plane_private_ips
}

output "worker_ips" {
  value = module.compute.worker_private_ips
}

output "gpu_worker_ips" {
  value = module.compute.gpu_worker_private_ips
}

output "efs_id" {
  value = aws_efs_file_system.shared.id
}

output "s3_bucket" {
  value = aws_s3_bucket.data.id
}
