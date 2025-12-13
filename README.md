# DaDude - Network Inventory & Monitoring System

Sistema di inventario e monitoraggio reti multi-tenant con supporto per agent WebSocket distribuiti e integrazione MikroTik.

## 🚀 Installazione Rapida

### Server DaDude (Proxmox LXC + Docker)

```bash
# Installazione su Proxmox (crea container LXC con Docker)
bash <(curl -fsSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude/deploy/proxmox/install-server.sh)
```

L'installer chiederà interattivamente:
- CTID container
- IP/Gateway/DNS
- Storage e memoria

### Agent DaDude WebSocket (Proxmox LXC + Docker)

```bash
# Installazione agent WebSocket (modalità agent-initiated, no porte in ascolto)
bash <(curl -fsSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude-agent/deploy/proxmox/install-websocket.sh)
```

L'installer chiederà interattivamente:
- URL Server DaDude (default: `http://dadude.domarc.it:8000`)
- Nome agent
- Configurazione rete (DHCP o statica)
- CTID, storage, bridge, VLAN

**Dopo l'installazione:**
1. Vai su `http://<server>:8000/agents`
2. Approva l'agent e assegnalo a un cliente
3. L'agent si connetterà automaticamente via WebSocket

---

## 📦 Installazione Manuale

### Server

```bash
# Clone repository
git clone https://github.com/grandir66/dadude.git /opt/dadude
cd /opt/dadude/dadude

# Crea ambiente
cat > .env << EOF
DATABASE_URL=sqlite+aiosqlite:///./data/dadude.db
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(openssl rand -base64 32)
EOF

# Avvia con Docker
docker compose up -d --build

# Verifica
curl http://localhost:8000/health
```

### Agent WebSocket

```bash
# Clone repository
git clone https://github.com/grandir66/dadude.git /opt/dadude-agent
cd /opt/dadude-agent/dadude-agent

# Crea ambiente
cat > .env << EOF
DADUDE_SERVER_URL=http://192.168.4.45:8000
DADUDE_AGENT_ID=agent-$(hostname)-$(date +%s | tail -c 5)
DADUDE_AGENT_NAME=my-agent
DADUDE_AGENT_TOKEN=$(openssl rand -base64 32 | tr -d '/+=' | head -c 32)
DADUDE_CONNECTION_MODE=websocket
DADUDE_DNS_SERVERS=8.8.8.8
EOF

# Crea docker-compose
cat > docker-compose.yml << 'EOF'
services:
  dadude-agent:
    build: .
    container_name: dadude-agent-ws
    restart: unless-stopped
    env_file: .env
    network_mode: host
    cap_add:
      - NET_RAW
      - NET_ADMIN
    volumes:
      - ./data:/var/lib/dadude-agent
      - /var/run/docker.sock:/var/run/docker.sock
      - .:/opt/dadude-agent
    command: ["python", "-m", "app.agent"]
EOF

# Avvia
docker compose up -d --build
```

---

## 🔧 Configurazione

### Variabili Server (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `DATABASE_URL` | URL database SQLite | `sqlite+aiosqlite:///./data/dadude.db` |
| `SECRET_KEY` | Chiave segreta per sessioni | (generata) |
| `ENCRYPTION_KEY` | Chiave per crittografia credenziali | (generata) |
| `DUDE_HOST` | Host MikroTik The Dude (opzionale) | - |
| `DUDE_PORT` | Porta API The Dude | `8728` |

### Variabili Agent WebSocket (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `DADUDE_SERVER_URL` | URL server DaDude | (richiesto) |
| `DADUDE_AGENT_ID` | ID univoco agent | (generato) |
| `DADUDE_AGENT_NAME` | Nome agent | hostname |
| `DADUDE_AGENT_TOKEN` | Token autenticazione | (generato) |
| `DADUDE_CONNECTION_MODE` | Modalità connessione | `websocket` |
| `DADUDE_DNS_SERVERS` | Server DNS per lookup | `8.8.8.8` |

---

## 🌐 Architettura WebSocket

```
┌─────────────────────────────────────────────────────────────┐
│                     DaDude Server                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐    │
│  │ Web UI   │  │ REST API │  │ WS Hub   │  │ Database │    │
│  │ (HTML)   │  │(FastAPI) │  │(Async)   │  │ (SQLite) │    │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘    │
│                                    ▲                         │
│                                    │ WebSocket               │
└────────────────────────────────────┼─────────────────────────┘
                                     │
        ┌────────────────────────────┼────────────────────────┐
        │                            │                        │
        ▼                            ▼                        ▼
┌───────────────┐          ┌───────────────┐         ┌───────────────┐
│ Agent Site A  │          │ Agent Site B  │         │ Agent Site C  │
│  (WebSocket)  │          │  (WebSocket)  │         │  (WebSocket)  │
│               │          │               │         │               │
│ • Nmap Scan   │          │ • Nmap Scan   │         │ • Nmap Scan   │
│ • WMI Probe   │          │ • WMI Probe   │         │ • WMI Probe   │
│ • SSH Probe   │          │ • SSH Probe   │         │ • SSH Probe   │
│ • SNMP Probe  │          │ • SNMP Probe  │         │ • SNMP Probe  │
│ • Port Scan   │          │ • Port Scan   │         │ • Port Scan   │
└───────────────┘          └───────────────┘         └───────────────┘
        │                            │                        │
        ▼                            ▼                        ▼
┌───────────────┐          ┌───────────────┐         ┌───────────────┐
│  Rete Site A  │          │  Rete Site B  │         │  Rete Site C  │
│ 192.168.1.0/24│          │ 10.0.0.0/24   │         │ 172.16.0.0/24 │
└───────────────┘          └───────────────┘         └───────────────┘
```

### Vantaggi WebSocket

- ✅ **Agent-initiated**: l'agent si connette al server, non viceversa
- ✅ **NAT-friendly**: funziona dietro firewall senza port forwarding
- ✅ **Sicuro**: solo porta 443 in uscita richiesta
- ✅ **Resiliente**: riconnessione automatica con exponential backoff
- ✅ **Real-time**: comandi e risultati bidirezionali

---

## 📋 Funzionalità

### Inventario
- ✅ Scansione reti (Nmap, ARP)
- ✅ Riconoscimento vendor da MAC address
- ✅ Reverse DNS lookup
- ✅ Port scanning TCP/UDP
- ✅ Identificazione OS

### Probing
- ✅ WMI (Windows) - CPU, RAM, dischi, servizi, software
- ✅ SSH (Linux/Unix) - Sistema, Docker, VM
- ✅ SNMP (Network devices) - Model, serial, firmware
- ✅ Auto-detect basato su porte aperte

### Agent WebSocket
- ✅ Connessione persistente al server
- ✅ Comandi remoti (scan, probe, update, restart)
- ✅ Auto-registrazione e approvazione
- ✅ Heartbeat e monitoraggio stato
- ✅ Self-update remoto

### Multi-tenant
- ✅ Gestione clienti separati
- ✅ Credenziali globali e per cliente
- ✅ Reti multiple per cliente
- ✅ Agent dedicati per cliente

---

## 🛠️ Comandi Utili

### Server

```bash
# Log server
docker logs -f dadude-server

# Riavvio
docker compose -f /opt/dadude/dadude/docker-compose.yml restart

# Aggiornamento
cd /opt/dadude && git pull && \
  docker compose -f dadude/docker-compose.yml up -d --build

# Verifica agent connessi
curl -s http://localhost:8000/api/v1/agents/ws/connected | python3 -m json.tool
```

### Agent

```bash
# Log agent
docker logs -f dadude-agent-ws

# Riavvio
docker restart dadude-agent-ws

# Aggiornamento (da dentro il container Proxmox)
pct exec <CTID> -- bash -c "cd /opt/dadude-agent && git pull && docker compose up -d --build"
```

---

## 🔒 Configurazione Traefik (Reverse Proxy)

Per esporre solo gli endpoint agent su internet (senza UI):

```yaml
# /etc/traefik/conf.d/dadude.yaml
http:
  routers:
    dadude-agents-ws:
      rule: "Host(`dadude.tuodominio.it`) && PathPrefix(`/api/v1/agents/ws`)"
      entryPoints:
        - websecure
      service: dadude
      tls:
        certResolver: letsencrypt
      priority: 100

    dadude-agents-api:
      rule: "Host(`dadude.tuodominio.it`) && PathPrefix(`/api/v1/agents`)"
      entryPoints:
        - websecure
      service: dadude
      tls:
        certResolver: letsencrypt
      priority: 90

  services:
    dadude:
      loadBalancer:
        servers:
          - url: "http://192.168.4.45:8000"
```

---

## 📄 Licenza

MIT License

## 🤝 Contributi

Contributi benvenuti! Apri una issue o pull request.
