#!/bin/bash
# Run this once on a fresh Ubuntu 22.04 / Debian 12 droplet as root.
set -e

echo "==> Installing Docker..."
apt-get update -qq
apt-get install -y ca-certificates curl gnupg
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
  > /etc/apt/sources.list.d/docker.list
apt-get update -qq
apt-get install -y docker-ce docker-ce-cli containerd.io

echo "==> Cloning repo..."
git clone https://github.com/grg-himal99/NepseUnofficialApi /opt/nepse-dashboard
cd /opt/nepse-dashboard

echo "==> Building Docker image..."
docker build -t nepse-dashboard:latest .

echo "==> Installing systemd service..."
cp deploy/nepse-dashboard.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable nepse-dashboard
systemctl start nepse-dashboard

echo ""
echo "Done! Dashboard running on port 8000."
echo "Check status: systemctl status nepse-dashboard"
echo "View logs:    journalctl -u nepse-dashboard -f"
