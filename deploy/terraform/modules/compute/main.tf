# Compute Module for Intuitive OS
# EC2 instances for control plane and workers

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

variable "name" {
  type    = string
  default = "intuitive-os"
}

variable "control_plane_count" {
  type    = number
  default = 1
}

variable "worker_count" {
  type    = number
  default = 2
}

variable "gpu_worker_count" {
  type    = number
  default = 0
}

variable "control_plane_instance_type" {
  type    = string
  default = "t3.medium"
}

variable "worker_instance_type" {
  type    = string
  default = "t3.small"
}

variable "gpu_instance_type" {
  type    = string
  default = "g4dn.xlarge"
}

variable "subnet_ids" {
  type = list(string)
}

variable "control_plane_sg_id" {
  type = string
}

variable "worker_sg_id" {
  type = string
}

variable "instance_profile" {
  type = string
}

variable "key_name" {
  type    = string
  default = ""
}

variable "talos_version" {
  type    = string
  default = "v1.6.0"
}

variable "tags" {
  type    = map(string)
  default = {}
}

locals {
  common_tags = merge({
    Project   = "IntuitiveOS"
    ManagedBy = "Terraform"
  }, var.tags)

  # Talos AMI - would be looked up or provided
  # In production, use data source to find latest Talos AMI
  talos_ami = "ami-0123456789abcdef0"  # Placeholder
}

# Get latest Ubuntu AMI (fallback for non-Talos testing)
data "aws_ami" "ubuntu" {
  most_recent = true
  owners      = ["099720109477"]  # Canonical

  filter {
    name   = "name"
    values = ["ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Control Plane Instances
resource "aws_instance" "control_plane" {
  count = var.control_plane_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.control_plane_instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.control_plane_sg_id]
  iam_instance_profile   = var.instance_profile
  key_name               = var.key_name != "" ? var.key_name : null

  root_block_device {
    volume_size = 50
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(templatefile("${path.module}/templates/control-plane-init.sh", {
    node_name   = "${var.name}-cp-${count.index}"
    node_role   = "controller"
    forge_mode  = "controller"
    ember_enabled = true
    cinder_enabled = true
  }))

  tags = merge(local.common_tags, {
    Name = "${var.name}-control-plane-${count.index}"
    Role = "control-plane"
  })

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# Worker Instances
resource "aws_instance" "worker" {
  count = var.worker_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.worker_instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.worker_sg_id]
  iam_instance_profile   = var.instance_profile
  key_name               = var.key_name != "" ? var.key_name : null

  root_block_device {
    volume_size = 30
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(templatefile("${path.module}/templates/worker-init.sh", {
    node_name      = "${var.name}-worker-${count.index}"
    node_role      = "worker"
    forge_mode     = "worker"
    control_plane  = aws_instance.control_plane[0].private_ip
  }))

  tags = merge(local.common_tags, {
    Name = "${var.name}-worker-${count.index}"
    Role = "worker"
  })

  depends_on = [aws_instance.control_plane]

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# GPU Worker Instances
resource "aws_instance" "gpu_worker" {
  count = var.gpu_worker_count

  ami                    = data.aws_ami.ubuntu.id
  instance_type          = var.gpu_instance_type
  subnet_id              = var.subnet_ids[count.index % length(var.subnet_ids)]
  vpc_security_group_ids = [var.worker_sg_id]
  iam_instance_profile   = var.instance_profile
  key_name               = var.key_name != "" ? var.key_name : null

  root_block_device {
    volume_size = 100
    volume_type = "gp3"
    encrypted   = true
  }

  user_data = base64encode(templatefile("${path.module}/templates/gpu-worker-init.sh", {
    node_name     = "${var.name}-gpu-${count.index}"
    node_role     = "gpu-worker"
    forge_mode    = "gpu-worker"
    control_plane = aws_instance.control_plane[0].private_ip
    gpu_enabled   = true
  }))

  tags = merge(local.common_tags, {
    Name     = "${var.name}-gpu-worker-${count.index}"
    Role     = "gpu-worker"
    GPU      = "true"
  })

  depends_on = [aws_instance.control_plane]

  lifecycle {
    ignore_changes = [ami, user_data]
  }
}

# Outputs
output "control_plane_ids" {
  value = aws_instance.control_plane[*].id
}

output "control_plane_private_ips" {
  value = aws_instance.control_plane[*].private_ip
}

output "control_plane_public_ips" {
  value = aws_instance.control_plane[*].public_ip
}

output "worker_ids" {
  value = aws_instance.worker[*].id
}

output "worker_private_ips" {
  value = aws_instance.worker[*].private_ip
}

output "gpu_worker_ids" {
  value = aws_instance.gpu_worker[*].id
}

output "gpu_worker_private_ips" {
  value = aws_instance.gpu_worker[*].private_ip
}
