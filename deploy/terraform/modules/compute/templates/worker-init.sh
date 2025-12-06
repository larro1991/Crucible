#!/bin/bash
# Intuitive OS Worker Node Bootstrap

set -euo pipefail

NODE_NAME="${node_name}"
NODE_ROLE="${node_role}"
FORGE_MODE="${forge_mode}"
CONTROL_PLANE="${control_plane}"

echo "=== Intuitive OS Worker Bootstrap ==="
echo "Node: $NODE_NAME"
echo "Control Plane: $CONTROL_PLANE"

# Write core principles
mkdir -p /etc/ember
cat > /etc/ember/principles <<EOF
HONESTY=true
KINDNESS=true
TRUST=true
TRANSPARENCY=true
EOF
chmod 444 /etc/ember/principles

# System updates
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get upgrade -y

# Install Docker
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

systemctl enable docker
systemctl start docker

# Install Python
apt-get install -y python3-pip python3-venv
pip3 install --upgrade pip

# Create directories
mkdir -p /opt/forge /var/ember /var/crucible /var/workloads
mkdir -p /opt/forge/{bin,config,data,logs}

# Write config
cat > /opt/forge/config/forge.env <<EOF
FORGE_MODE=$FORGE_MODE
CINDER_AGENT=true
CONTROL_PLANE=$CONTROL_PLANE
NODE_NAME=$NODE_NAME
NODE_ROLE=$NODE_ROLE
LOG_LEVEL=info
EOF

# Create CINDER agent service
cat > /etc/systemd/system/cinder-agent.service <<EOF
[Unit]
Description=CINDER Node Agent
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/opt/forge/config/forge.env
ExecStart=/opt/forge/bin/cinder-agent
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Wait for control plane to be ready
echo "Waiting for control plane..."
sleep 60

# Get join token from control plane (would be passed securely in production)
# For now, use k3s agent join
curl -sfL https://get.k3s.io | K3S_URL="https://$CONTROL_PLANE:6443" K3S_TOKEN_FILE=/tmp/k3s-token sh -s - agent || true

# Label node
echo "=== Worker Bootstrap Complete ==="
