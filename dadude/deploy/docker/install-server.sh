#!/bin/bash
#
# DaDude Server - Installazione Docker
# 
# Uso:
#   curl -sSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude/deploy/docker/install-server.sh | bash
#
# Oppure con parametri:
#   curl -sSL ... | bash -s -- --ip 192.168.4.45 --port 8000
#

set -e

# Colori
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default
INSTALL_DIR="/opt/dadude"
SERVER_IP=""
SERVER_PORT="8000"
DUDE_HOST=""
DUDE_PORT="8728"
DUDE_USER=""
DUDE_PASS=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --ip) SERVER_IP="$2"; shift 2 ;;
        --port) SERVER_PORT="$2"; shift 2 ;;
        --dude-host) DUDE_HOST="$2"; shift 2 ;;
        --dude-port) DUDE_PORT="$2"; shift 2 ;;
        --dude-user) DUDE_USER="$2"; shift 2 ;;
        --dude-pass) DUDE_PASS="$2"; shift 2 ;;
        --dir) INSTALL_DIR="$2"; shift 2 ;;
        -h|--help)
            echo "DaDude Server Installer"
            echo ""
            echo "Uso: $0 [opzioni]"
            echo ""
            echo "Opzioni:"
            echo "  --ip IP          IP del server (auto-detect se non specificato)"
            echo "  --port PORT      Porta del server (default: 8000)"
            echo "  --dude-host HOST Host The Dude (opzionale)"
            echo "  --dude-port PORT Porta The Dude (default: 8728)"
            echo "  --dude-user USER Username The Dude"
            echo "  --dude-pass PASS Password The Dude"
            echo "  --dir DIR        Directory installazione (default: /opt/dadude)"
            exit 0
            ;;
        *) echo "Opzione sconosciuta: $1"; exit 1 ;;
    esac
done

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════╗"
echo "║     DaDude Server - Installazione        ║"
echo "╚══════════════════════════════════════════╝"
echo -e "${NC}"

# Verifica requisiti
echo -e "${YELLOW}[1/5] Verifica requisiti...${NC}"

if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker non installato. Installo...${NC}"
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose non installato. Installo...${NC}"
    apt-get update && apt-get install -y docker-compose-plugin
fi

if ! command -v git &> /dev/null; then
    echo -e "${YELLOW}Installo git...${NC}"
    apt-get update && apt-get install -y git
fi

# Auto-detect IP
if [ -z "$SERVER_IP" ]; then
    SERVER_IP=$(ip route get 1 | awk '{print $7;exit}' 2>/dev/null || hostname -I | awk '{print $1}')
fi

echo -e "${GREEN}✓ Requisiti OK${NC}"
echo -e "  Server IP: ${SERVER_IP}"

# Clone repository
echo -e "${YELLOW}[2/5] Scarico DaDude...${NC}"

if [ -d "$INSTALL_DIR" ]; then
    echo -e "${YELLOW}Directory esistente, aggiorno...${NC}"
    cd "$INSTALL_DIR"
    git pull || true
else
    git clone https://github.com/grandir66/dadude.git "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

cd dadude

# Crea .env
echo -e "${YELLOW}[3/5] Configuro ambiente...${NC}"

cat > .env << EOF
# DaDude Server Configuration
DATABASE_URL=sqlite:///./data/dadude.db
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -hex 16)

# The Dude Connection (opzionale)
DUDE_HOST=${DUDE_HOST}
DUDE_PORT=${DUDE_PORT}
DUDE_USERNAME=${DUDE_USER}
DUDE_PASSWORD=${DUDE_PASS}
EOF

# Crea directory dati
mkdir -p data
chmod 755 data

# Crea docker-compose.yml
echo -e "${YELLOW}[4/5] Creo configurazione Docker...${NC}"

cat > docker-compose.yml << 'EOF'
services:
  dadude-server:
    build: .
    container_name: dadude-server
    restart: unless-stopped
    network_mode: host
    volumes:
      - ./data:/app/data
      - ./.env:/app/.env:ro
    environment:
      - TZ=Europe/Rome
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3
EOF

# Disabilita iptables Docker per evitare conflitti
mkdir -p /etc/docker
if [ ! -f /etc/docker/daemon.json ]; then
    echo '{"iptables": false}' > /etc/docker/daemon.json
    systemctl restart docker
    sleep 3
fi

# Build e start
echo -e "${YELLOW}[5/5] Avvio DaDude Server...${NC}"

docker compose build --quiet
docker compose up -d

# Attendi avvio
echo -e "${YELLOW}Attendo avvio server...${NC}"
for i in {1..30}; do
    if curl -s http://localhost:${SERVER_PORT}/health &>/dev/null; then
        break
    fi
    sleep 1
done

# Verifica
if curl -s http://localhost:${SERVER_PORT}/health &>/dev/null; then
    echo -e "${GREEN}"
    echo "╔══════════════════════════════════════════╗"
    echo "║    ✅ DaDude Server Installato!          ║"
    echo "╚══════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    echo -e "  ${GREEN}Dashboard:${NC} http://${SERVER_IP}:${SERVER_PORT}/"
    echo -e "  ${GREEN}API Docs:${NC}  http://${SERVER_IP}:${SERVER_PORT}/docs"
    echo -e "  ${GREEN}Health:${NC}    http://${SERVER_IP}:${SERVER_PORT}/health"
    echo ""
    echo -e "  ${YELLOW}Directory:${NC} ${INSTALL_DIR}/dadude"
    echo ""
    echo "Comandi utili:"
    echo "  cd ${INSTALL_DIR}/dadude"
    echo "  docker compose logs -f    # Visualizza log"
    echo "  docker compose restart    # Riavvia"
    echo "  docker compose down       # Ferma"
    echo ""
else
    echo -e "${RED}Errore: Server non raggiungibile${NC}"
    echo "Verifica i log: docker compose logs"
    exit 1
fi

