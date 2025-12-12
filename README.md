# DaDude - Network Inventory & Monitoring System

Sistema di inventario e monitoraggio reti multi-tenant con supporto per MikroTik The Dude e agent distribuiti.

## 🚀 Installazione Rapida

### Server DaDude (Docker)

```bash
# Installazione one-liner
curl -sSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude/deploy/docker/install-server.sh | bash

# Con parametri personalizzati
curl -sSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude/deploy/docker/install-server.sh | bash -s -- \
  --ip 192.168.4.45 \
  --port 8000
```

### Agent DaDude (Docker)

```bash
# Installazione one-liner (richiede server URL e token)
curl -sSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude-agent/deploy/docker/install-agent.sh | bash -s -- \
  --server http://192.168.4.45:8000 \
  --token YOUR_AGENT_TOKEN \
  --name agent-rete1

# Con DNS personalizzato
curl -sSL https://raw.githubusercontent.com/grandir66/dadude/main/dadude-agent/deploy/docker/install-agent.sh | bash -s -- \
  --server http://192.168.4.45:8000 \
  --token YOUR_AGENT_TOKEN \
  --dns 192.168.1.1
```

## 📦 Installazione Manuale

### Server

```bash
# Clone repository
git clone https://github.com/grandir66/dadude.git /opt/dadude
cd /opt/dadude/dadude

# Crea ambiente
cp .env.example .env
# Modifica .env con le tue configurazioni

# Avvia con Docker
docker compose up -d

# Verifica
curl http://localhost:8000/health
```

### Agent

```bash
# Clone repository
git clone https://github.com/grandir66/dadude.git /opt/dadude-agent
cd /opt/dadude-agent/dadude-agent

# Crea ambiente
cat > .env << EOF
DADUDE_SERVER_URL=http://192.168.4.45:8000
DADUDE_AGENT_TOKEN=your_token_here
DADUDE_AGENT_ID=agent-001
DADUDE_AGENT_NAME=my-agent
DADUDE_AGENT_PORT=8080
DADUDE_DNS_SERVERS=8.8.8.8
EOF

# Avvia con Docker
docker compose up -d

# Verifica
curl http://localhost:8080/health
```

## 🔧 Configurazione

### Variabili Server (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `DATABASE_URL` | URL database SQLite | `sqlite:///./data/dadude.db` |
| `SECRET_KEY` | Chiave segreta per sessioni | (generata) |
| `ENCRYPTION_KEY` | Chiave per crittografia credenziali | (generata) |
| `DUDE_HOST` | Host MikroTik The Dude (opzionale) | - |
| `DUDE_PORT` | Porta API The Dude | `8728` |
| `DUDE_USERNAME` | Username The Dude | - |
| `DUDE_PASSWORD` | Password The Dude | - |

### Variabili Agent (.env)

| Variabile | Descrizione | Default |
|-----------|-------------|---------|
| `DADUDE_SERVER_URL` | URL server DaDude | (richiesto) |
| `DADUDE_AGENT_TOKEN` | Token autenticazione | (richiesto) |
| `DADUDE_AGENT_ID` | ID univoco agent | (generato) |
| `DADUDE_AGENT_NAME` | Nome agent | hostname |
| `DADUDE_AGENT_PORT` | Porta API agent | `8080` |
| `DADUDE_DNS_SERVERS` | Server DNS per lookup | `8.8.8.8` |

## 🌐 Architettura

```
┌─────────────────────────────────────────────────────────┐
│                    DaDude Server                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Dashboard  │  │   API REST  │  │  Database   │     │
│  │   (Web UI)  │  │  (FastAPI)  │  │  (SQLite)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────┐  ┌─────────────────┐
│ MikroTik Agent  │  │  Docker Agent   │
│   (RouterOS)    │  │   (Linux/CT)    │
│                 │  │                 │
│ • ARP Scan      │  │ • Nmap Scan     │
│ • Netwatch      │  │ • WMI Probe     │
│ • DNS Lookup    │  │ • SSH Probe     │
│                 │  │ • SNMP Probe    │
└─────────────────┘  └─────────────────┘
         │                    │
         ▼                    ▼
┌─────────────────────────────────────────────────────────┐
│                   Rete Cliente                          │
│  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐  ┌─────┐          │
│  │ PC  │  │ NAS │  │ AP  │  │ SW  │  │ SRV │          │
│  └─────┘  └─────┘  └─────┘  └─────┘  └─────┘          │
└─────────────────────────────────────────────────────────┘
```

## 📋 Funzionalità

### Inventario
- ✅ Scansione reti (ARP, Nmap)
- ✅ Riconoscimento vendor da MAC address
- ✅ Reverse DNS lookup
- ✅ Port scanning TCP/UDP
- ✅ Identificazione OS

### Probing
- ✅ WMI (Windows)
- ✅ SSH (Linux/Unix)
- ✅ SNMP (Network devices)
- ✅ Auto-detect basato su porte aperte

### Monitoraggio
- ✅ Integrazione MikroTik Netwatch
- ✅ Agent distribuiti
- ✅ Dashboard real-time

### Multi-tenant
- ✅ Gestione clienti separati
- ✅ Credenziali globali e per cliente
- ✅ Reti multiple per cliente

## 🛠️ Comandi Utili

```bash
# Log server
docker compose -f /opt/dadude/dadude/docker-compose.yml logs -f

# Log agent
docker compose -f /opt/dadude-agent/dadude-agent/docker-compose.yml logs -f

# Riavvio server
docker compose -f /opt/dadude/dadude/docker-compose.yml restart

# Aggiornamento
cd /opt/dadude && git pull && docker compose -f dadude/docker-compose.yml up -d --build
```

## 📄 Licenza

MIT License

## 🤝 Contributi

Contributi benvenuti! Apri una issue o pull request.

