#!/bin/bash
# Script per aggiornare agent su Proxmox da dentro il container agent
# Uso: ./update-agent-proxmox.sh <proxmox_ip> <container_id> [ssh_user] [ssh_password]

set -e

PROXMOX_IP="${1:-}"
CONTAINER_ID="${2:-}"
SSH_USER="${3:-root}"
SSH_PASSWORD="${4:-}"

if [ -z "$PROXMOX_IP" ] || [ -z "$CONTAINER_ID" ]; then
    echo "Uso: $0 <proxmox_ip> <container_id> [ssh_user] [ssh_password]"
    echo ""
    echo "Esempi:"
    echo "  $0 192.168.40.15 600 root"
    echo "  $0 192.168.40.15 610 root mypassword"
    echo ""
    exit 1
fi

echo "=========================================="
echo "Aggiornamento Agent su Proxmox"
echo "Server: $PROXMOX_IP"
echo "Container: $CONTAINER_ID"
echo "=========================================="

# Comando completo
if [ -n "$SSH_PASSWORD" ]; then
    sshpass -p "$SSH_PASSWORD" ssh -o StrictHostKeyChecking=no "$SSH_USER@$PROXMOX_IP" "pct exec $CONTAINER_ID -- bash -c '
        cd /opt/dadude-agent/dadude-agent 2>/dev/null || cd /opt/dadude-agent || exit 1
        echo \"1. Fetching latest changes...\"
        git fetch origin main 2>&1
        echo \"2. Checking versions...\"
        CURRENT=\$(git rev-parse HEAD 2>/dev/null || echo \"unknown\")
        LATEST=\$(git rev-parse origin/main 2>/dev/null || echo \"unknown\")
        echo \"   Current: \${CURRENT:0:8}\"
        echo \"   Latest:  \${LATEST:0:8}\"
        if [ \"\$CURRENT\" != \"\$LATEST\" ] && [ \"\$LATEST\" != \"unknown\" ]; then
            echo \"3. Update available! Applying...\"
            git reset --hard origin/main 2>&1
            echo \"4. Restarting agent container...\"
            docker restart dadude-agent 2>&1 || docker compose restart 2>&1
            echo \"✅ Update completed\"
        else
            echo \"3. Already up to date\"
        fi
    '"
else
    ssh -o StrictHostKeyChecking=no "$SSH_USER@$PROXMOX_IP" "pct exec $CONTAINER_ID -- bash -c '
        cd /opt/dadude-agent/dadude-agent 2>/dev/null || cd /opt/dadude-agent || exit 1
        echo \"1. Fetching latest changes...\"
        git fetch origin main 2>&1
        echo \"2. Checking versions...\"
        CURRENT=\$(git rev-parse HEAD 2>/dev/null || echo \"unknown\")
        LATEST=\$(git rev-parse origin/main 2>/dev/null || echo \"unknown\")
        echo \"   Current: \${CURRENT:0:8}\"
        echo \"   Latest:  \${LATEST:0:8}\"
        if [ \"\$CURRENT\" != \"\$LATEST\" ] && [ \"\$LATEST\" != \"unknown\" ]; then
            echo \"3. Update available! Applying...\"
            git reset --hard origin/main 2>&1
            echo \"4. Restarting agent container...\"
            docker restart dadude-agent 2>&1 || docker compose restart 2>&1
            echo \"✅ Update completed\"
        else
            echo \"3. Already up to date\"
        fi
    '"
fi

echo ""
echo "=========================================="
echo "Completato!"
echo "=========================================="

