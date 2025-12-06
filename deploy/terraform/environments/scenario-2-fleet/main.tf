# Scenario 2: Multi-Node Fleet
# Controller + 2 Workers for fleet testing
# Cost: ~$80/month

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
      Environment = "scenario-2"
      Scenario    = "multi-node-fleet"
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

# VPC with multiple AZs
module "vpc" {
  source = "../../modules/vpc"

  name               = "intuitive-os-s2"
  vpc_cidr           = "10.1.0.0/16"
  availability_zones = ["us-east-1a", "us-east-1b"]
  enable_nat_gateway = true
}

# Security
module "security" {
  source = "../../modules/security"

  name     = "intuitive-os-s2"
  vpc_id   = module.vpc.vpc_id
  vpc_cidr = module.vpc.vpc_cidr
}

# Controller + Workers
module "compute" {
  source = "../../modules/compute"

  name                        = "intuitive-os-s2"
  control_plane_count         = 1
  worker_count                = 2
  gpu_worker_count            = 0
  control_plane_instance_type = "t3.medium"
  worker_instance_type        = "t3.small"
  subnet_ids                  = module.vpc.private_subnet_ids
  control_plane_sg_id         = module.security.control_plane_sg_id
  worker_sg_id                = module.security.worker_sg_id
  instance_profile            = module.security.node_instance_profile
  key_name                    = var.key_name
}

# Application Load Balancer for external access
resource "aws_lb" "main" {
  name               = "intuitive-os-s2-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [module.security.lb_sg_id]
  subnets            = module.vpc.public_subnet_ids

  tags = {
    Name = "intuitive-os-s2-alb"
  }
}

resource "aws_lb_target_group" "api" {
  name     = "intuitive-os-s2-api"
  port     = 6443
  protocol = "HTTPS"
  vpc_id   = module.vpc.vpc_id

  health_check {
    path                = "/healthz"
    protocol            = "HTTPS"
    healthy_threshold   = 2
    unhealthy_threshold = 10
  }
}

resource "aws_lb_target_group_attachment" "control_plane" {
  count            = length(module.compute.control_plane_ids)
  target_group_arn = aws_lb_target_group.api.arn
  target_id        = module.compute.control_plane_ids[count.index]
  port             = 6443
}

# Outputs
output "load_balancer_dns" {
  value = aws_lb.main.dns_name
}

output "control_plane_ips" {
  value = module.compute.control_plane_private_ips
}

output "worker_ips" {
  value = module.compute.worker_private_ips
}

output "nat_gateway_ip" {
  value = module.vpc.nat_gateway_ip
}
