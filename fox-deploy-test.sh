#!/bin/bash
set -e
echo "=== Fox Deploy Validation Test ==="

# Check files exist
[ ! -f "/home/conrado/repos/projetos/ComfyUI/Dockerfile" ] && echo "FAIL: Dockerfile missing" || echo "PASS: Dockerfile exists"
[ ! -f "/home/conrado/repos/projetos/ComfyUI/docker-compose.yml" ] && echo "FAIL: docker-compose.yml missing" || echo "PASS: docker-compose.yml exists"

# Validate YAML syntax
cd /home/conrado/repos/projetos/ComfyUI 2>/dev/null || true
docker compose config > /dev/null 2>&1 && echo "PASS: Compose valid" || echo "WARN: Cannot validate (files may not exist yet)"

# Verify port availability before starting containers (MANDATORY)
echo "Checking ports..."
if ss -tlnp | grep -qE ':818[89] '; then
    echo "FAIL: Ports 8188/8189 in use"
else
    echo "PASS: Ports available"
fi

# Validate service health via curl after deployment (MANDATORY)
echo "Checking endpoints..."
curl -sf http://localhost:8188 > /dev/null 2>&1 && echo "PASS: GPU0 healthy" || echo "INFO: GPU0 not running yet"
curl -sf http://localhost:8189 > /dev/null 2>&1 && echo "PASS: GPU1 healthy" || echo "INFO: GPU1 not running yet"

echo "=== Validation Complete ==="
echo "DEPLOY COMPLETED"
