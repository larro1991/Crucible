# Crucible VM Setup Guide - TrueNAS Scale

This guide walks through setting up a Crucible VM on TrueNAS Scale.

---

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                      TrueNAS Scale Server                        │
│                                                                  │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │                    Crucible VM                             │ │
│   │                                                            │ │
│   │   OS: Ubuntu Server 24.04 LTS                             │ │
│   │   Purpose: AI development verification                     │ │
│   │                                                            │ │
│   │   Services:                                                │ │
│   │   • Crucible MCP Server (port 8080)                       │ │
│   │   • Docker (for isolated execution)                        │ │
│   │   • SSH (port 22)                                          │ │
│   │                                                            │ │
│   │   Storage:                                                 │ │
│   │   • /crucible/fixtures    - Test fixtures                 │ │
│   │   • /crucible/learnings   - Persistent knowledge          │ │
│   │                                                            │ │
│   └───────────────────────────────────────────────────────────┘ │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Prerequisites

- TrueNAS Scale with virtualization enabled
- At least 4GB RAM available for VM
- At least 32GB storage available
- Network access for the VM

---

## Step 1: Create the VM in TrueNAS

### 1.1 Download Ubuntu Server ISO

1. Go to https://ubuntu.com/download/server
2. Download Ubuntu Server 24.04 LTS ISO
3. Upload to TrueNAS: **System Settings → Shell**
   ```bash
   # Or use the web UI to upload to a dataset
   wget -O /mnt/pool/isos/ubuntu-24.04-server.iso \
     https://releases.ubuntu.com/24.04/ubuntu-24.04-live-server-amd64.iso
   ```

### 1.2 Create VM

1. Navigate to **Virtualization → Virtual Machines**
2. Click **Add**
3. Configure:

| Setting | Value |
|---------|-------|
| Name | `crucible` |
| Guest OS | Linux |
| System Clock | Local |
| Boot Method | UEFI |
| Shutdown Timeout | 90 |
| Start on Boot | Yes |
| Enable VNC | Yes |
| VNC Port | 5900 (auto) |

### 1.3 CPU and Memory

| Setting | Value |
|---------|-------|
| Virtual CPUs | 2-4 |
| Cores | 1 |
| Threads | 1 |
| Memory Size | 4096 MB (4GB minimum) |

### 1.4 Disks

1. Add disk:
   - **Type**: AHCI
   - **Zvol Location**: Select your pool
   - **Size**: 32 GB minimum (64 GB recommended)

### 1.5 Network

1. Add NIC:
   - **Adapter Type**: VirtIO
   - **NIC to Attach**: Select your bridge/interface

### 1.6 Installation Media

1. Add CD-ROM:
   - **CD-ROM Path**: Path to Ubuntu ISO

### 1.7 Create and Start

1. Click **Save**
2. Start the VM
3. Use VNC to access console

---

## Step 2: Install Ubuntu Server

### 2.1 Boot and Install

1. Connect via VNC
2. Select "Install Ubuntu Server"
3. Choose language, keyboard
4. Network: Use DHCP or configure static IP
5. Storage: Use entire disk
6. Profile setup:
   - Name: `crucible`
   - Server name: `crucible`
   - Username: `crucible`
   - Password: (set secure password)
7. Enable OpenSSH server
8. No additional snaps needed
9. Complete installation and reboot

### 2.2 Remove Installation Media

1. In TrueNAS, edit VM
2. Remove CD-ROM device
3. Restart VM if needed

---

## Step 3: Initial VM Configuration

### 3.1 Connect via SSH

```bash
ssh crucible@<VM_IP_ADDRESS>
```

### 3.2 Update System

```bash
sudo apt update && sudo apt upgrade -y
```

### 3.3 Install Required Packages

```bash
# Base packages
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    git \
    curl \
    wget \
    htop \
    vim

# Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker crucible

# Log out and back in for docker group
exit
```

### 3.4 Reconnect and Verify Docker

```bash
ssh crucible@<VM_IP_ADDRESS>
docker run hello-world
```

---

## Step 4: Install Crucible

### 4.1 Clone Repository

```bash
cd ~
git clone https://github.com/larro1991/Crucible.git
cd Crucible
```

### 4.2 Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 4.3 Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4.4 Create Data Directories

```bash
sudo mkdir -p /crucible/{fixtures,learnings}
sudo chown -R crucible:crucible /crucible

# Symlink from repo
ln -sf /crucible/fixtures ~/Crucible/fixtures
ln -sf /crucible/learnings ~/Crucible/learnings
```

### 4.5 Test Run

```bash
cd ~/Crucible
source venv/bin/activate
python -m server.main --help
```

---

## Step 5: Configure as Service

### 5.1 Create Systemd Service

```bash
sudo tee /etc/systemd/system/crucible.service << 'EOF'
[Unit]
Description=Crucible MCP Server
After=network.target docker.service
Wants=docker.service

[Service]
Type=simple
User=crucible
Group=crucible
WorkingDirectory=/home/crucible/Crucible
Environment=PATH=/home/crucible/Crucible/venv/bin:/usr/local/bin:/usr/bin:/bin
ExecStart=/home/crucible/Crucible/venv/bin/python -m server.main
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF
```

### 5.2 Enable and Start

```bash
sudo systemctl daemon-reload
sudo systemctl enable crucible
sudo systemctl start crucible
sudo systemctl status crucible
```

---

## Step 6: Configure Claude Code Connection

### 6.1 Option A: SSH Tunnel (Recommended)

From your Windows machine, create an SSH tunnel:

```powershell
ssh -L 8080:localhost:8080 crucible@<VM_IP_ADDRESS>
```

Then configure Claude Code to use `localhost:8080`.

### 6.2 Option B: Direct Network Access

If the VM is on your local network:

1. Note the VM's IP address
2. Configure Claude Code MCP settings to point to `http://<VM_IP>:8080`

### 6.3 Claude Code MCP Configuration

Add to your Claude Code configuration (`.claude/mcp.json` or equivalent):

```json
{
  "mcpServers": {
    "crucible": {
      "command": "ssh",
      "args": [
        "-L", "8080:localhost:8080",
        "crucible@<VM_IP_ADDRESS>",
        "cd /home/crucible/Crucible && ./venv/bin/python -m server.main"
      ]
    }
  }
}
```

Or for stdio transport:

```json
{
  "mcpServers": {
    "crucible": {
      "command": "ssh",
      "args": [
        "crucible@<VM_IP_ADDRESS>",
        "cd /home/crucible/Crucible && ./venv/bin/python -m server.main"
      ]
    }
  }
}
```

---

## Step 7: Verify Installation

### 7.1 Check Service Status

```bash
ssh crucible@<VM_IP_ADDRESS>
sudo systemctl status crucible
```

### 7.2 Check Logs

```bash
sudo journalctl -u crucible -f
```

### 7.3 Test from Claude Code

Once configured, you should be able to use tools like:
- `crucible_execute` - Run code
- `crucible_verify` - Verify code
- `crucible_capture` - Capture fixtures
- `crucible_note` - Store learnings
- `crucible_recall` - Retrieve learnings

---

## Maintenance

### Update Crucible

```bash
ssh crucible@<VM_IP_ADDRESS>
cd ~/Crucible
git pull
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart crucible
```

### Backup Data

```bash
# On TrueNAS or via SSH
tar -czvf crucible-data-$(date +%Y%m%d).tar.gz /crucible/
```

### View Resource Usage

```bash
htop
docker stats
```

---

## Troubleshooting

### Service Won't Start

```bash
# Check logs
sudo journalctl -u crucible -n 50

# Try running manually
cd ~/Crucible
source venv/bin/activate
python -m server.main
```

### Docker Permission Denied

```bash
# Ensure user is in docker group
groups crucible
sudo usermod -aG docker crucible
# Log out and back in
```

### Can't Connect from Claude Code

1. Check VM is running: `ping <VM_IP>`
2. Check service is running: `systemctl status crucible`
3. Check firewall: `sudo ufw status`
4. Check SSH tunnel is active

### Out of Disk Space

```bash
# Check disk usage
df -h

# Clean Docker
docker system prune -a

# Check fixture/learning sizes
du -sh /crucible/*
```

---

## Security Notes

1. **SSH Keys**: Consider using SSH keys instead of passwords
   ```bash
   ssh-copy-id crucible@<VM_IP_ADDRESS>
   ```

2. **Firewall**: Enable UFW
   ```bash
   sudo ufw allow ssh
   sudo ufw allow 8080/tcp  # Only if direct access needed
   sudo ufw enable
   ```

3. **Updates**: Keep system updated
   ```bash
   sudo apt update && sudo apt upgrade -y
   ```

4. **Docker Security**: Isolated execution uses restrictive Docker settings:
   - No network access
   - Memory limits
   - Read-only filesystem
   - CPU limits

---

## VM Resource Recommendations

| Use Case | vCPUs | RAM | Disk |
|----------|-------|-----|------|
| Light (testing) | 2 | 4 GB | 32 GB |
| Standard | 4 | 8 GB | 64 GB |
| Heavy (many containers) | 8 | 16 GB | 128 GB |

---

## Next Steps

Once Crucible is running:

1. Capture some fixtures from the Linux environment
2. Store initial learnings
3. Test code execution through Claude Code
4. Build verification into your workflow

See main documentation for tool usage details.
