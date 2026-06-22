#!/bin/bash
# Run this on the server whenever you push new changes.
set -e

cd /opt/nepse-dashboard
git pull origin master
docker build -t nepse-dashboard:latest .
systemctl restart nepse-dashboard
echo "Updated and restarted."
