# Scenario 1: Single Node VM
# Simple deployment for basic testing
# Cost: ~$30/month

terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # Uncomment for remote state
  # backend "s3" {
  #   bucket = "intuitive-os-terraform-state"
  #   key    = "scenario-1/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "IntuitiveOS"
      Environment = "scenario-1"
      Scenario    = "single-node"
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

# VPC (simplified - single AZ)
module "vpc" {
  source = "../../modules/vpc"

  name               = "intuitive-os-s1"
  vpc_cidr           = "10.0.0.0/16"
  availability_zones = ["us-east-1a"]
  enable_nat_gateway = false  # Save costs - use public subnet only
}

# Security
module "security" {
  source = "../../modules/security"

  name     = "intuitive-os-s1"
  vpc_id   = module.vpc.vpc_id
  vpc_cidr = module.vpc.vpc_cidr
}

# Single node with everything
module "compute" {
  source = "../../modules/compute"

  name                        = "intuitive-os-s1"
  control_plane_count         = 1
  worker_count                = 0  # All-in-one
  gpu_worker_count            = 0
  control_plane_instance_type = "t3.medium"
  subnet_ids                  = module.vpc.public_subnet_ids
  control_plane_sg_id         = module.security.control_plane_sg_id
  worker_sg_id                = module.security.worker_sg_id
  instance_profile            = module.security.node_instance_profile
  key_name                    = var.key_name
}

# Outputs
output "control_plane_ip" {
  value = module.compute.control_plane_public_ips[0]
}

output "ssh_command" {
  value = var.key_name != "" ? "ssh -i ~/.ssh/${var.key_name}.pem ubuntu@${module.compute.control_plane_public_ips[0]}" : "No SSH key configured"
}

output "k3s_kubeconfig" {
  value = "scp ubuntu@${module.compute.control_plane_public_ips[0]}:/etc/rancher/k3s/k3s.yaml ~/.kube/intuitive-os-s1.yaml"
}
