#!/bin/bash
# Intuitive OS GPU Worker Bootstrap
# For AI/ML workloads with NVIDIA GPU

set -euo pipefail

NODE_NAME="${node_name}"
NODE_ROLE="${node_role}"
FORGE_MODE="${forge_mode}"
CONTROL_PLANE="${control_plane}"
GPU_ENABLED="${gpu_enabled}"

echo "=== Intuitive OS GPU Worker Bootstrap ==="
echo "Node: $NODE_NAME"
echo "GPU Enabled: $GPU_ENABLED"

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

# Install NVIDIA drivers
apt-get install -y linux-headers-$(uname -r)
apt-get install -y nvidia-driver-535 nvidia-utils-535

# Install NVIDIA Container Toolkit
distribution=$(. /etc/os-release;echo $ID$VERSION_ID)
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/$distribution/libnvidia-container.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

apt-get update
apt-get install -y nvidia-container-toolkit

# Install Docker with NVIDIA runtime
apt-get install -y apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin

# Configure Docker to use NVIDIA runtime
nvidia-ctk runtime configure --runtime=docker
systemctl restart docker

# Install Python with ML dependencies
apt-get install -y python3-pip python3-venv
pip3 install --upgrade pip

# Create directories
mkdir -p /opt/forge /var/ember /var/crucible /var/models /var/workloads
mkdir -p /opt/forge/{bin,config,data,logs}

# Write config
cat > /opt/forge/config/forge.env <<EOF
FORGE_MODE=$FORGE_MODE
CINDER_AGENT=true
GPU_ENABLED=$GPU_ENABLED
LLM_LOCAL=true
CONTROL_PLANE=$CONTROL_PLANE
NODE_NAME=$NODE_NAME
NODE_ROLE=$NODE_ROLE
LOG_LEVEL=info
CUDA_VISIBLE_DEVICES=all
EOF

# Create GPU-enabled CINDER agent service
cat > /etc/systemd/system/cinder-agent.service <<EOF
[Unit]
Description=CINDER GPU Node Agent
After=docker.service network-online.target nvidia-persistenced.service
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

# Create local LLM service
cat > /etc/systemd/system/local-llm.service <<EOF
[Unit]
Description=Local LLM Service (Ollama)
After=docker.service nvidia-persistenced.service

[Service]
Type=simple
ExecStart=/usr/bin/docker run --rm --gpus all -v /var/models:/root/.ollama -p 11434:11434 ollama/ollama
Restart=always
RestartSec=30

[Install]
WantedBy=multi-user.target
EOF

# Wait for control plane
echo "Waiting for control plane..."
sleep 60

# Join cluster
curl -sfL https://get.k3s.io | K3S_URL="https://$CONTROL_PLANE:6443" K3S_TOKEN_FILE=/tmp/k3s-token sh -s - agent || true

echo "=== GPU Worker Bootstrap Complete ==="
nvidia-smi || echo "GPU not yet available (may need reboot)"
