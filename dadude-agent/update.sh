#!/bin/bash
# DaDude Agent - Update Script
# Scarica l'ultima versione da GitHub e ricostruisce il container

set -e

AGENT_DIR="/opt/dadude-agent"
TEMP_DIR="/tmp/dadude-update-$$"
GITHUB_REPO="https://github.com/grandir66/dadude.git"

echo "╔══════════════════════════════════════════╗"
echo "║     DaDude Agent - Aggiornamento         ║"
echo "╚══════════════════════════════════════════╝"

# Verifica directory
if [ ! -d "$AGENT_DIR" ]; then
    echo "❌ Errore: $AGENT_DIR non trovata"
    exit 1
fi

# Backup .env
echo "[1/5] Backup configurazione..."
if [ -f "$AGENT_DIR/.env" ]; then
    cp "$AGENT_DIR/.env" /tmp/dadude-agent.env.backup
    echo "      ✓ .env salvato"
else
    echo "      ⚠ .env non trovato"
fi

# Scarica ultima versione
echo "[2/5] Scarico ultima versione da GitHub..."
rm -rf "$TEMP_DIR"
git clone --depth 1 "$GITHUB_REPO" "$TEMP_DIR" 2>/dev/null
echo "      ✓ Repository clonato"

# Verifica nuova versione
NEW_VERSION=$(grep 'AGENT_VERSION = ' "$TEMP_DIR/dadude-agent/app/main.py" | head -1 | cut -d'"' -f2)
echo "      Nuova versione: $NEW_VERSION"

# Ferma container
echo "[3/5] Fermo container..."
cd "$AGENT_DIR"
docker compose down 2>/dev/null || true
echo "      ✓ Container fermato"

# Aggiorna file
echo "[4/5] Aggiorno file..."
rm -rf "$AGENT_DIR/app" "$AGENT_DIR/config" "$AGENT_DIR/Dockerfile" "$AGENT_DIR/requirements.txt" "$AGENT_DIR/docker-compose.yml"
cp -r "$TEMP_DIR/dadude-agent/app" "$AGENT_DIR/"
cp -r "$TEMP_DIR/dadude-agent/config" "$AGENT_DIR/"
cp "$TEMP_DIR/dadude-agent/Dockerfile" "$AGENT_DIR/"
cp "$TEMP_DIR/dadude-agent/requirements.txt" "$AGENT_DIR/"
cp "$TEMP_DIR/dadude-agent/docker-compose.yml" "$AGENT_DIR/"
cp "$TEMP_DIR/dadude-agent/update.sh" "$AGENT_DIR/" 2>/dev/null || true
echo "      ✓ File aggiornati"

# Ripristina .env
if [ -f /tmp/dadude-agent.env.backup ]; then
    cp /tmp/dadude-agent.env.backup "$AGENT_DIR/.env"
    echo "      ✓ .env ripristinato"
fi

# Cleanup
rm -rf "$TEMP_DIR"

# Ricostruisci e avvia
echo "[5/5] Ricostruisco e avvio..."
cd "$AGENT_DIR"
docker compose build --no-cache
docker compose up -d

# Attendi avvio
sleep 5

# Verifica
echo ""
echo "╔══════════════════════════════════════════╗"
echo "║     ✅ Aggiornamento completato!         ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Verifica stato:"
curl -s http://localhost:8080/health | python3 -c "import sys,json; d=json.load(sys.stdin); print(f\"  Agent: {d['agent_name']}\"); print(f\"  Versione: {d['version']}\"); print(f\"  Stato: {d['status']}\")" 2>/dev/null || echo "  ⚠ Agent non raggiungibile"
echo ""

