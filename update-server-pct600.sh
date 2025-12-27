#!/bin/bash
#
# Script per aggiornare il server DaDude su PCT 600 (192.168.40.1)
# Uso: ./update-server-pct600.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SERVER_HOST="192.168.40.1"
PCT_ID="600"
CONTAINER_NAME="dadude"
REPO_PATH="/app/repo"

echo -e "${YELLOW}=== Aggiornamento Server DaDude PCT 600 ===${NC}"
echo "Host: ${SERVER_HOST}"
echo "Container: ${CONTAINER_NAME}"
echo ""

# Verifica connessione
echo -e "${YELLOW}Verifico connessione al server...${NC}"
if ! ssh -o ConnectTimeout=5 root@${SERVER_HOST} "echo 'OK'" > /dev/null 2>&1; then
    echo -e "${RED}Errore: Impossibile connettersi a ${SERVER_HOST}${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Connessione OK${NC}"
echo ""

# Verifica che il container esista
echo -e "${YELLOW}Verifico container...${NC}"
if ! ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- docker ps --format '{{.Names}}' | grep -q '^${CONTAINER_NAME}$'" 2>/dev/null; then
    echo -e "${RED}Errore: Container ${CONTAINER_NAME} non trovato${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container trovato${NC}"
echo ""

# Mostra versione corrente
echo -e "${YELLOW}Versione corrente sul server:${NC}"
CURRENT_COMMIT=$(ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- bash -c 'docker exec ${CONTAINER_NAME} bash -c \"cd ${REPO_PATH} && git rev-parse HEAD 2>/dev/null || echo unknown\"'")
echo "Commit: ${CURRENT_COMMIT:0:7}"
echo ""

# Pull aggiornamenti
echo -e "${YELLOW}Scarico aggiornamenti...${NC}"
ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- bash -c 'docker exec ${CONTAINER_NAME} bash -c \"git config --global --add safe.directory ${REPO_PATH} && cd ${REPO_PATH} && git pull origin main\"'"

# Verifica nuova versione
echo ""
echo -e "${YELLOW}Nuova versione sul server:${NC}"
NEW_COMMIT=$(ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- bash -c 'docker exec ${CONTAINER_NAME} bash -c \"cd ${REPO_PATH} && git rev-parse HEAD\"'")
echo "Commit: ${NEW_COMMIT:0:7}"

if [ "$CURRENT_COMMIT" = "$NEW_COMMIT" ]; then
    echo -e "${GREEN}✓ Server già aggiornato${NC}"
else
    echo -e "${GREEN}✓ Aggiornato da ${CURRENT_COMMIT:0:7} a ${NEW_COMMIT:0:7}${NC}"
fi
echo ""

# Riavvia container
echo -e "${YELLOW}Riavvio container...${NC}"
ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- docker restart ${CONTAINER_NAME}"
echo -e "${GREEN}✓ Container riavviato${NC}"
echo ""

# Attendi che il container sia pronto
echo -e "${YELLOW}Attendo che il container sia pronto...${NC}"
sleep 5

# Verifica che il container sia attivo
if ssh root@${SERVER_HOST} "pct exec ${PCT_ID} -- docker ps --format '{{.Status}}' --filter name=${CONTAINER_NAME} | grep -q 'Up'"; then
    echo -e "${GREEN}✓ Container attivo${NC}"
else
    echo -e "${RED}⚠ Avviso: Verifica manualmente lo stato del container${NC}"
fi
echo ""

echo -e "${GREEN}=== Aggiornamento completato ===${NC}"

