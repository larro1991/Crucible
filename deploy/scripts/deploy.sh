#!/bin/bash
# Intuitive OS Deployment Script
# Usage: ./deploy.sh <scenario> [options]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(dirname "$SCRIPT_DIR")"
PROJECT_ROOT="$(dirname "$DEPLOY_DIR")"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

usage() {
    cat <<EOF
Intuitive OS Deployment Script

Usage: $0 <command> [options]

Commands:
    local       Deploy locally with Docker Compose
    aws-s1      Deploy AWS Scenario 1 (Single Node)
    aws-s2      Deploy AWS Scenario 2 (Multi-Node Fleet)
    aws-s3      Deploy AWS Scenario 3 (Production)
    destroy     Destroy infrastructure
    status      Show deployment status

Options:
    -r, --region    AWS region (default: us-east-1)
    -k, --key       SSH key name for AWS
    -y, --yes       Skip confirmation prompts
    -h, --help      Show this help

Examples:
    $0 local                    # Local Docker deployment
    $0 aws-s1 -k mykey          # AWS Scenario 1 with SSH key
    $0 aws-s3 -r us-west-2      # AWS Scenario 3 in us-west-2
    $0 destroy aws-s1           # Destroy Scenario 1

EOF
    exit 0
}

check_prerequisites() {
    log_info "Checking prerequisites..."

    local missing=()

    command -v docker >/dev/null 2>&1 || missing+=("docker")
    command -v terraform >/dev/null 2>&1 || missing+=("terraform")
    command -v aws >/dev/null 2>&1 || missing+=("aws-cli")

    if [[ ${#missing[@]} -gt 0 ]]; then
        log_error "Missing required tools: ${missing[*]}"
        exit 1
    fi

    log_info "All prerequisites met"
}

deploy_local() {
    log_info "Deploying locally with Docker Compose..."

    cd "$DEPLOY_DIR/docker"

    # Create principles file
    mkdir -p principles
    cat > principles/principles <<EOF
HONESTY=true
KINDNESS=true
TRUST=true
TRANSPARENCY=true
EOF

    # Build and start
    docker compose build
    docker compose up -d

    log_info "Waiting for services to be healthy..."
    sleep 30

    docker compose ps

    log_info "Local deployment complete!"
    log_info "Services:"
    log_info "  - Forge:    http://localhost:8080"
    log_info "  - EMBER:    http://localhost:8081"
    log_info "  - CINDER:   http://localhost:8082"
    log_info "  - Crucible: http://localhost:8084"
}

deploy_aws() {
    local scenario=$1
    local region=${AWS_REGION:-us-east-1}
    local key_name=${SSH_KEY:-""}

    log_info "Deploying AWS $scenario in $region..."

    local tf_dir="$DEPLOY_DIR/terraform/environments/$scenario"

    if [[ ! -d "$tf_dir" ]]; then
        log_error "Scenario directory not found: $tf_dir"
        exit 1
    fi

    cd "$tf_dir"

    # Initialize Terraform
    terraform init

    # Plan
    local plan_args="-var aws_region=$region"
    [[ -n "$key_name" ]] && plan_args+=" -var key_name=$key_name"

    terraform plan $plan_args -out=tfplan

    # Confirm
    if [[ "${SKIP_CONFIRM:-false}" != "true" ]]; then
        read -p "Apply this plan? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warn "Deployment cancelled"
            exit 0
        fi
    fi

    # Apply
    terraform apply tfplan

    # Show outputs
    terraform output

    log_info "AWS deployment complete!"
}

destroy_aws() {
    local scenario=$1

    log_info "Destroying AWS $scenario..."

    local tf_dir="$DEPLOY_DIR/terraform/environments/$scenario"

    if [[ ! -d "$tf_dir" ]]; then
        log_error "Scenario directory not found: $tf_dir"
        exit 1
    fi

    cd "$tf_dir"

    if [[ "${SKIP_CONFIRM:-false}" != "true" ]]; then
        read -p "Are you sure you want to destroy $scenario? [y/N] " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            log_warn "Destroy cancelled"
            exit 0
        fi
    fi

    terraform destroy -auto-approve

    log_info "Destroy complete"
}

show_status() {
    log_info "Deployment Status"
    echo

    # Local
    echo "=== Local (Docker) ==="
    if docker compose -f "$DEPLOY_DIR/docker/docker-compose.yaml" ps 2>/dev/null | grep -q "Up"; then
        docker compose -f "$DEPLOY_DIR/docker/docker-compose.yaml" ps
    else
        echo "Not running"
    fi
    echo

    # AWS scenarios
    for scenario in scenario-1-single scenario-2-fleet scenario-3-production; do
        echo "=== AWS: $scenario ==="
        local tf_dir="$DEPLOY_DIR/terraform/environments/$scenario"
        if [[ -f "$tf_dir/terraform.tfstate" ]]; then
            cd "$tf_dir"
            terraform output 2>/dev/null || echo "No outputs"
        else
            echo "Not deployed"
        fi
        echo
    done
}

# Parse arguments
COMMAND=${1:-}
shift || true

AWS_REGION="us-east-1"
SSH_KEY=""
SKIP_CONFIRM="false"

while [[ $# -gt 0 ]]; do
    case $1 in
        -r|--region) AWS_REGION="$2"; shift 2 ;;
        -k|--key) SSH_KEY="$2"; shift 2 ;;
        -y|--yes) SKIP_CONFIRM="true"; shift ;;
        -h|--help) usage ;;
        *) log_error "Unknown option: $1"; usage ;;
    esac
done

# Execute command
case $COMMAND in
    local)
        check_prerequisites
        deploy_local
        ;;
    aws-s1)
        check_prerequisites
        deploy_aws "scenario-1-single"
        ;;
    aws-s2)
        check_prerequisites
        deploy_aws "scenario-2-fleet"
        ;;
    aws-s3)
        check_prerequisites
        deploy_aws "scenario-3-production"
        ;;
    destroy)
        SCENARIO=${1:-}
        if [[ -z "$SCENARIO" ]]; then
            log_error "Specify scenario to destroy"
            exit 1
        fi
        destroy_aws "$SCENARIO"
        ;;
    status)
        show_status
        ;;
    *)
        usage
        ;;
esac
