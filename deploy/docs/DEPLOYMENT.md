# Intuitive OS Deployment Guide

## Overview

This guide covers deploying the Intuitive OS stack (Forge, EMBER, CINDER, Crucible) in various environments.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    EMBER (Brain)                         │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐       │
│  │ CodeAgent   │ │ Research    │ │ Analysis    │       │
│  └─────────────┘ └─────────────┘ └─────────────┘       │
│         ↓               ↓               ↓               │
│  ┌──────────────────────────────────────────────┐      │
│  │         Core Principles Gate (4)              │      │
│  │   Honesty | Kindness | Trust | Transparency   │      │
│  └──────────────────────────────────────────────┘      │
├─────────────────────────────────────────────────────────┤
│                    FORGE (Host)                          │
├─────────────────────────────────────────────────────────┤
│                    CINDER (Fleet)                        │
├─────────────────────────────────────────────────────────┤
│                  INTUITIVE OS (Base)                     │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Docker 24.0+ and Docker Compose
- Terraform 1.5+
- AWS CLI (for cloud deployments)
- SSH key pair (for AWS)

## Deployment Options

### 1. Local Development (Docker Compose)

Best for: Testing, development, learning the system

```bash
cd deploy
./scripts/deploy.sh local
```

Services will be available at:
- Forge: http://localhost:8080
- EMBER: http://localhost:8081
- CINDER Controller: http://localhost:8082
- Crucible: http://localhost:8084

### 2. AWS Scenario 1: Single Node

Best for: Simple testing, minimal cost (~$30/month)

```bash
./scripts/deploy.sh aws-s1 -k your-ssh-key
```

Architecture:
- 1x t3.medium (Control Plane + All Services)
- Public subnet only
- No NAT gateway (cost savings)

### 3. AWS Scenario 2: Multi-Node Fleet

Best for: Fleet testing, failover testing (~$80/month)

```bash
./scripts/deploy.sh aws-s2 -k your-ssh-key
```

Architecture:
- 1x t3.medium (Control Plane)
- 2x t3.small (Workers)
- Private subnets with NAT
- Application Load Balancer

### 4. AWS Scenario 3: Production

Best for: Full production deployment (~$500-1000/month)

```bash
./scripts/deploy.sh aws-s3 -k your-ssh-key
```

Architecture:
- 2x t3.large (HA Control Plane)
- 3x t3.medium (Workers)
- 2x g4dn.xlarge (GPU Workers) - optional
- Multi-AZ deployment
- EFS shared storage
- S3 for backups
- Network Load Balancer for K8s API

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `FORGE_MODE` | controller, worker, standalone | standalone |
| `EMBER_ENABLED` | Enable EMBER orchestration | true |
| `CINDER_ENABLED` | Enable CINDER fleet | true |
| `LOG_LEVEL` | info, debug, warn, error | info |

### Core Principles (Immutable)

These are set at deploy time and cannot be changed:

```
HONESTY=true
KINDNESS=true
TRUST=true
TRANSPARENCY=true
```

Every action passes through the principles gate before execution.

## Operations

### Check Status

```bash
./scripts/deploy.sh status
```

### Destroy Infrastructure

```bash
# Destroy specific scenario
./scripts/deploy.sh destroy scenario-1-single

# Local
docker compose -f deploy/docker/docker-compose.yaml down -v
```

### View Logs

```bash
# Local
docker compose logs -f forge

# AWS (SSH to node)
journalctl -u forge -f
```

### Scale Workers (Scenario 2/3)

Edit `terraform.tfvars`:
```hcl
worker_count = 5
```

Then apply:
```bash
terraform apply
```

## Troubleshooting

### Services not starting

1. Check Docker is running: `docker ps`
2. Check logs: `docker compose logs <service>`
3. Verify principles file exists: `ls deploy/docker/principles/`

### AWS deployment fails

1. Check AWS credentials: `aws sts get-caller-identity`
2. Check Terraform state: `terraform state list`
3. Check EC2 console for instance status

### Nodes not joining cluster

1. Check security groups allow traffic
2. Verify control plane is healthy
3. Check cloud-init logs: `/var/log/cloud-init-output.log`

## Monitoring

### Prometheus Metrics

All services expose metrics on `/metrics`:
- Forge: :8080/metrics
- EMBER: :8081/metrics
- CINDER: :8082/metrics
- Crucible: :8084/metrics

### Health Checks

```bash
curl http://localhost:8080/health
curl http://localhost:8081/health
curl http://localhost:8082/health
curl http://localhost:8084/health
```

## Security Considerations

1. **Principles are immutable** - Cannot be changed at runtime
2. **Network isolation** - Use private subnets in production
3. **Encryption** - EBS and S3 encryption enabled by default
4. **IAM** - Minimal permissions per node role
5. **No SSH in production** - Use Talos API for management

## Next Steps

After deployment:

1. Verify all services are healthy
2. Test EMBER agent orchestration
3. Test CINDER fleet operations
4. Configure monitoring/alerting
5. Set up backups

## License

Intuitive OS is built on:
- Talos Linux (MPL 2.0) - Clean commercial licensing
- Linux Kernel (GPL v2) - Required for any OS
- Our code (MIT) - Full commercial use allowed
