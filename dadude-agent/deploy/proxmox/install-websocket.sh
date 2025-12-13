#!/bin/bash
#
# DaDude Agent v2.0 - Installazione WebSocket mTLS
# Installa agent in modalità WebSocket (agent-initiated)
#

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  DaDude Agent v2.0 - WebSocket mTLS Installer            ║"
echo "║  Modalità: Agent-Initiated (no porte in ascolto)         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Parametri di default
CTID=""
HOSTNAME="dadude-agent-ws"
STORAGE="local-lvm"
TEMPLATE_STORAGE="local"
MEMORY=512
DISK=4
BRIDGE="vmbr0"
VLAN=""
IP=""
GATEWAY=""
DNS="8.8.8.8"
SERVER_URL=""
AGENT_NAME=""
AGENT_TOKEN=""

# Parse argomenti
while [[ $# -gt 0 ]]; do
    case $1 in
        --ctid) CTID="$2"; shift 2 ;;
        --hostname) HOSTNAME="$2"; shift 2 ;;
        --storage) STORAGE="$2"; shift 2 ;;
        --memory) MEMORY="$2"; shift 2 ;;
        --disk) DISK="$2"; shift 2 ;;
        --bridge) BRIDGE="$2"; shift 2 ;;
        --vlan) VLAN="$2"; shift 2 ;;
        --ip) IP="$2"; shift 2 ;;
        --gateway) GATEWAY="$2"; shift 2 ;;
        --dns) DNS="$2"; shift 2 ;;
        --server-url) SERVER_URL="$2"; shift 2 ;;
        --agent-name) AGENT_NAME="$2"; shift 2 ;;
        --agent-token) AGENT_TOKEN="$2"; shift 2 ;;
        --help)
            echo "Uso: $0 [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  --ctid ID          ID container (auto se non specificato)"
            echo "  --hostname NAME    Hostname container"
            echo "  --server-url URL   URL server DaDude (es: http://192.168.4.45:8000)"
            echo "  --agent-name NAME  Nome agent"
            echo "  --agent-token TOK  Token agent (opzionale, auto-generato)"
            echo "  --bridge BRIDGE    Bridge di rete (default: vmbr0)"
            echo "  --vlan ID          VLAN tag (opzionale)"
            echo "  --ip IP/MASK       IP statico (es: 192.168.1.100/24)"
            echo "  --gateway IP       Gateway"
            echo "  --dns IP           DNS server"
            exit 0
            ;;
        *) echo "Opzione sconosciuta: $1"; exit 1 ;;
    esac
done

# Interattivo se mancano parametri
if [ -z "$SERVER_URL" ]; then
    read -p "URL Server DaDude (es: http://192.168.4.45:8000): " SERVER_URL
fi

if [ -z "$AGENT_NAME" ]; then
    read -p "Nome Agent: " AGENT_NAME
fi

if [ -z "$BRIDGE" ]; then
    read -p "Bridge di rete [vmbr0]: " BRIDGE
    BRIDGE=${BRIDGE:-vmbr0}
fi

if [ -z "$VLAN" ]; then
    read -p "VLAN tag (vuoto se nessuna): " VLAN
fi

if [ -z "$IP" ]; then
    read -p "IP/MASK (es: 192.168.99.20/24): " IP
fi

if [ -z "$GATEWAY" ]; then
    read -p "Gateway: " GATEWAY
fi

if [ -z "$DNS" ]; then
    read -p "DNS [8.8.8.8]: " DNS
    DNS=${DNS:-8.8.8.8}
fi

# Genera token se non fornito
if [ -z "$AGENT_TOKEN" ]; then
    AGENT_TOKEN=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
    echo -e "${YELLOW}Token generato: ${AGENT_TOKEN}${NC}"
fi

# Trova CTID libero
if [ -z "$CTID" ]; then
    CTID=$(pvesh get /cluster/nextid)
fi

# Genera agent ID
AGENT_ID="agent-ws-${AGENT_NAME}-$(date +%s | tail -c 5)"

echo ""
echo -e "${GREEN}Configurazione:${NC}"
echo "  CTID:        $CTID"
echo "  Hostname:    $HOSTNAME"
echo "  Agent ID:    $AGENT_ID"
echo "  Agent Name:  $AGENT_NAME"
echo "  Server URL:  $SERVER_URL"
echo "  Network:     $BRIDGE${VLAN:+ (VLAN $VLAN)}"
echo "  IP:          $IP"
echo "  Gateway:     $GATEWAY"
echo "  DNS:         $DNS"
echo "  Mode:        WebSocket mTLS (v2.0)"
echo ""

read -p "Procedere con l'installazione? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Annullato."
    exit 1
fi

# Trova template
echo -e "\n${BLUE}[1/6] Verifico template...${NC}"

TEMPLATE=""
for t in "debian-12-standard" "debian-11-standard" "ubuntu-24.04-standard" "ubuntu-22.04-standard"; do
    if pveam list $TEMPLATE_STORAGE 2>/dev/null | grep -q "$t"; then
        TEMPLATE=$(pveam list $TEMPLATE_STORAGE | grep "$t" | head -1 | awk '{print $1}')
        break
    fi
done

if [ -z "$TEMPLATE" ]; then
    echo "Scarico template Debian 12..."
    pveam update
    TEMPLATE_NAME=$(pveam available | grep "debian-12-standard" | head -1 | awk '{print $2}')
    if [ -n "$TEMPLATE_NAME" ]; then
        pveam download $TEMPLATE_STORAGE $TEMPLATE_NAME
        TEMPLATE="${TEMPLATE_STORAGE}:vztmpl/${TEMPLATE_NAME}"
    else
        echo -e "${RED}Errore: nessun template disponibile${NC}"
        exit 1
    fi
fi

echo -e "${GREEN}Usando template: $TEMPLATE${NC}"

# Configura rete
NET_CONFIG="name=eth0,bridge=${BRIDGE}"
if [ -n "$VLAN" ]; then
    NET_CONFIG="${NET_CONFIG},tag=${VLAN}"
fi
if [ -n "$IP" ]; then
    NET_CONFIG="${NET_CONFIG},ip=${IP},gw=${GATEWAY}"
fi

# Crea container
echo -e "\n${BLUE}[2/6] Creo container LXC...${NC}"

pct create $CTID $TEMPLATE \
    --hostname $HOSTNAME \
    --storage $STORAGE \
    --memory $MEMORY \
    --cores 1 \
    --net0 "$NET_CONFIG" \
    --nameserver "$DNS" \
    --features nesting=1,keyctl=1 \
    --unprivileged 0 \
    --start 1

sleep 5

# Attendi avvio
echo -e "\n${BLUE}[3/6] Attendo avvio container...${NC}"
for i in {1..30}; do
    if pct exec $CTID -- echo "ok" &>/dev/null; then
        break
    fi
    sleep 2
done

# Installa Docker
echo -e "\n${BLUE}[4/6] Installo Docker...${NC}"

pct exec $CTID -- bash -c '
apt-get update
apt-get install -y ca-certificates curl gnupg git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
'

# Clona repository
echo -e "\n${BLUE}[5/6] Clono repository e configuro...${NC}"

pct exec $CTID -- bash -c "
mkdir -p /opt/dadude-agent
cd /opt
git clone https://github.com/grandir66/dadude.git dadude-temp
cp -r dadude-temp/dadude-agent/* /opt/dadude-agent/
rm -rf dadude-temp
"

# Crea .env per modalità WebSocket
pct exec $CTID -- bash -c "cat > /opt/dadude-agent/.env << 'EOF'
# DaDude Agent v2.0 - WebSocket Mode
DADUDE_SERVER_URL=${SERVER_URL}
DADUDE_AGENT_ID=${AGENT_ID}
DADUDE_AGENT_NAME=${AGENT_NAME}
DADUDE_AGENT_TOKEN=${AGENT_TOKEN}
DADUDE_CONNECTION_MODE=websocket
DADUDE_LOG_LEVEL=INFO
DADUDE_DNS_SERVERS=${DNS}

# Local storage
DADUDE_DATA_DIR=/var/lib/dadude-agent

# SFTP Fallback (opzionale)
SFTP_ENABLED=false
EOF"

# Modifica docker-compose per modalità WebSocket
pct exec $CTID -- bash -c "cat > /opt/dadude-agent/docker-compose.yml << 'EOF'
version: '3.8'

services:
  dadude-agent:
    build: .
    container_name: dadude-agent-ws
    restart: unless-stopped
    env_file: .env
    # Modalità WebSocket - nessuna porta esposta!
    # L'agent si connette al server, non viceversa
    volumes:
      - ./data:/var/lib/dadude-agent
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/opt/dadude-agent
    # Entry point WebSocket
    command: [\"python\", \"-m\", \"app.agent\"]
    healthcheck:
      test: [\"CMD\", \"python\", \"-c\", \"import sys; sys.exit(0)\"]
      interval: 60s
      timeout: 10s
      retries: 3
EOF"

# Crea directory dati
pct exec $CTID -- mkdir -p /opt/dadude-agent/data

# Build e avvia
echo -e "\n${BLUE}[6/6] Build e avvio container Docker...${NC}"

pct exec $CTID -- bash -c "cd /opt/dadude-agent && docker compose build && docker compose up -d"

sleep 5

# Verifica
echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║    ✅ Installazione Completata!                          ║${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "Container ID:  $CTID"
echo "Hostname:      $HOSTNAME"
echo "Agent ID:      $AGENT_ID"
echo "Agent Name:    $AGENT_NAME"
echo "Agent Token:   $AGENT_TOKEN"
echo "Mode:          WebSocket mTLS (agent-initiated)"
echo ""
echo -e "${YELLOW}IMPORTANTE: Nessuna porta in ascolto!${NC}"
echo "L'agent si connette al server via WebSocket."
echo ""
echo "Prossimi passi:"
echo "1. Verifica i log: pct exec $CTID -- docker logs dadude-agent-ws"
echo "2. L'agent tenterà di registrarsi automaticamente"
echo "3. Approva l'agent dal pannello DaDude: /agents"
echo "4. Dopo approvazione, l'agent richiederà certificato mTLS"
echo ""
echo "Comandi utili:"
echo "  pct exec $CTID -- docker logs -f dadude-agent-ws"
echo "  pct exec $CTID -- docker exec dadude-agent-ws cat /var/lib/dadude-agent/queue.db"
echo ""

