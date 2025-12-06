#!/bin/bash
# Intuitive OS Control Plane Bootstrap
# This script initializes a control plane node

set -euo pipefail

NODE_NAME="${node_name}"
NODE_ROLE="${node_role}"
FORGE_MODE="${forge_mode}"
EMBER_ENABLED="${ember_enabled}"
CINDER_ENABLED="${cinder_enabled}"

echo "=== Intuitive OS Control Plane Bootstrap ==="
echo "Node: $NODE_NAME"
echo "Role: $NODE_ROLE"

# Write core principles (immutable)
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

# Enable Docker
systemctl enable docker
systemctl start docker

# Install Python dependencies
apt-get install -y python3-pip python3-venv
pip3 install --upgrade pip

# Create directories
mkdir -p /opt/forge /var/ember /var/crucible /var/cinder
mkdir -p /opt/forge/{bin,config,data,logs}

# Write Forge config
cat > /opt/forge/config/forge.env <<EOF
FORGE_MODE=$FORGE_MODE
EMBER_ENABLED=$EMBER_ENABLED
CINDER_ENABLED=$CINDER_ENABLED
CRUCIBLE_ENABLED=true
NODE_NAME=$NODE_NAME
NODE_ROLE=$NODE_ROLE
LOG_LEVEL=info
DATA_DIR=/opt/forge/data
EOF

# Create systemd service for Forge
cat > /etc/systemd/system/forge.service <<EOF
[Unit]
Description=Forge AI Management Daemon
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=simple
EnvironmentFile=/opt/forge/config/forge.env
ExecStart=/opt/forge/bin/forge-daemon
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Create CINDER controller service
cat > /etc/systemd/system/cinder-controller.service <<EOF
[Unit]
Description=CINDER Fleet Controller
After=forge.service
Requires=forge.service

[Service]
Type=simple
EnvironmentFile=/opt/forge/config/forge.env
ExecStart=/opt/forge/bin/cinder-controller
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# Install k3s for lightweight Kubernetes (alternative to full Talos)
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="server --disable traefik" sh -

# Wait for k3s
sleep 30

# Copy kubeconfig
mkdir -p /root/.kube
cp /etc/rancher/k3s/k3s.yaml /root/.kube/config
chmod 600 /root/.kube/config

# Create intuitive-os namespace
kubectl create namespace intuitive-os --dry-run=client -o yaml | kubectl apply -f -

# Label this node
kubectl label node $(hostname) node-role.kubernetes.io/control-plane=true --overwrite
kubectl label node $(hostname) forge.intuitive-os.io/mode=controller --overwrite

echo "=== Control Plane Bootstrap Complete ==="
echo "K3s API: https://$(hostname -I | awk '{print $1}'):6443"
