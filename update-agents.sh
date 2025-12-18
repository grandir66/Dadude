#!/bin/bash
# Script per aggiornare manualmente gli agent DaDude
# Uso: ./update-agents.sh [agent_ip] [agent_type]

set -e

AGENT_IP="${1:-}"
AGENT_TYPE="${2:-docker}"  # docker o mikrotik

if [ -z "$AGENT_IP" ]; then
    echo "Uso: $0 <agent_ip> [agent_type]"
    echo ""
    echo "Esempi:"
    echo "  $0 192.168.4.100 docker     # Agent Docker standalone"
    echo "  $0 192.168.4.100 mikrotik   # Agent su router MikroTik"
    echo ""
    echo "Per agent MikroTik, devi prima connetterti al router:"
    echo "  ssh admin@192.168.4.100"
    echo "  /container/restart [find where name~\"dadude\"]"
    exit 1
fi

echo "=========================================="
echo "Aggiornamento Agent DaDude"
echo "IP: $AGENT_IP"
echo "Tipo: $AGENT_TYPE"
echo "=========================================="

if [ "$AGENT_TYPE" = "mikrotik" ]; then
    echo ""
    echo "Per agent su MikroTik, connettiti al router e esegui:"
    echo ""
    echo "  ssh admin@$AGENT_IP"
    echo ""
    echo "Poi sul router MikroTik:"
    echo "  /container/restart [find where name~\"dadude\"]"
    echo ""
    echo "OPPURE per aggiornare il codice:"
    echo "  /container/exec [find where name~\"dadude\"] git pull origin main"
    echo "  /container/restart [find where name~\"dadude\"]"
    echo ""
    
elif [ "$AGENT_TYPE" = "docker" ]; then
    echo ""
    echo "Tentativo connessione SSH a $AGENT_IP..."
    
    # Prova SSH
    if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@"$AGENT_IP" "echo 'SSH OK'" 2>/dev/null; then
        echo "✓ Connessione SSH riuscita"
        echo ""
        echo "Eseguendo aggiornamento..."
        
        ssh root@"$AGENT_IP" << 'EOF'
            # Trova directory agent
            if [ -d "/opt/dadude-agent" ]; then
                AGENT_DIR="/opt/dadude-agent"
            elif [ -d "/opt/dadude/dadude-agent" ]; then
                AGENT_DIR="/opt/dadude/dadude-agent"
            else
                echo "❌ Directory agent non trovata"
                exit 1
            fi
            
            echo "Directory agent: $AGENT_DIR"
            cd "$AGENT_DIR"
            
            # Git pull
            echo "Eseguendo git pull..."
            git pull origin main || echo "⚠️ Git pull fallito, continuo comunque..."
            
            # Trova container agent
            CONTAINER=$(docker ps --format "{{.Names}}" | grep -i agent | head -1)
            
            if [ -z "$CONTAINER" ]; then
                echo "⚠️ Container agent non trovato in esecuzione"
                echo "Verifica con: docker ps -a | grep agent"
            else
                echo "Container trovato: $CONTAINER"
                echo "Riavviando container..."
                docker restart "$CONTAINER" || docker compose -f docker-compose.yml restart
            fi
            
            echo "✓ Aggiornamento completato"
EOF
        
    else
        echo "❌ Connessione SSH fallita"
        echo ""
        echo "Prova manualmente:"
        echo "  ssh root@$AGENT_IP"
        echo "  cd /opt/dadude-agent  # o /opt/dadude/dadude-agent"
        echo "  git pull origin main"
        echo "  docker restart \$(docker ps --format '{{.Names}}' | grep -i agent | head -1)"
        echo ""
        echo "OPPURE se usa docker-compose:"
        echo "  ssh root@$AGENT_IP"
        echo "  cd /opt/dadude-agent"
        echo "  git pull origin main"
        echo "  docker compose down && docker compose up -d --build"
    fi
    
else
    echo "❌ Tipo agent non riconosciuto: $AGENT_TYPE"
    echo "Usa: docker o mikrotik"
    exit 1
fi

echo ""
echo "=========================================="
echo "Completato!"
echo "=========================================="

