# DaDude v2.0 Migration Plan
## SQLite → PostgreSQL + HTML → Vue.js 3

**Data creazione**: 2024-12-18
**Branch**: `claude/dadude-v2-postgres-vue-lVlLs`

---

## 1. Analisi Struttura Progetto Attuale

### 1.1 Struttura Directory
```
Dadude/
├── dadude/                    # Server Backend (FastAPI)
│   ├── app/
│   │   ├── main.py            # Entry point FastAPI
│   │   ├── config.py          # Configurazione Pydantic Settings
│   │   ├── models/
│   │   │   ├── database.py    # SQLAlchemy models principali (SQLite)
│   │   │   ├── inventory.py   # Models inventory dispositivi
│   │   │   ├── backup_models.py # Models backup configurazioni
│   │   │   ├── schemas.py     # Pydantic schemas API
│   │   │   └── customer_schemas.py
│   │   ├── routers/           # API endpoints
│   │   ├── services/          # Business logic
│   │   └── templates/         # HTML templates (Jinja2)
│   ├── docker-compose.yml     # Docker config attuale
│   └── requirements.txt       # Python dependencies
│
└── dadude-agent/              # Agent remoto (non modificare)
    └── ...
```

---

## 2. File che Usano SQLite

### 2.1 Database Models (MODIFICARE)
| File | Linee | Priorità | Note |
|------|-------|----------|------|
| `dadude/app/models/database.py` | 494 | ALTA | Modelli principali Customer, Network, Credential, DeviceAssignment, AgentAssignment, ScanResult, DiscoveredDevice |
| `dadude/app/models/inventory.py` | 609 | ALTA | InventoryDevice, NetworkInterface, DiskInfo, WindowsDetails, LinuxDetails, MikroTikDetails |
| `dadude/app/models/backup_models.py` | 270 | ALTA | DeviceBackup, BackupSchedule, BackupJob, BackupTemplate |

### 2.2 Services con Query Database (MODIFICARE)
| File | Query Type | Note |
|------|------------|------|
| `dadude/app/services/customer_service.py` | CRUD customers, networks, credentials, agents | ~1600 linee, SQLAlchemy ORM sync |
| `dadude/app/services/device_backup_service.py` | Backup CRUD | SQLAlchemy ORM |
| `dadude/app/services/alert_service.py` | AlertHistory CRUD | SQLAlchemy ORM |
| `dadude/app/services/settings_service.py` | Settings persistence | SQLAlchemy ORM |

### 2.3 Routers con Accesso DB (MODIFICARE)
| File | Linee | Endpoints |
|------|-------|-----------|
| `dadude/app/routers/agents.py` | 86,457 | /api/v1/agents/* |
| `dadude/app/routers/customers.py` | 68,197 | /api/v1/customers/* |
| `dadude/app/routers/inventory.py` | 77,731 | /api/v1/inventory/* |
| `dadude/app/routers/device_backup.py` | 25,411 | /api/v1/backups/* |
| `dadude/app/routers/mikrotik.py` | 17,920 | /api/v1/mikrotik/* |
| `dadude/app/routers/discovery.py` | 6,468 | /api/v1/discovery/* |
| `dadude/app/routers/dashboard.py` | 19,521 | /dashboard/* (HTML) |
| `dadude/app/routers/webhook.py` | 5,689 | /api/v1/webhook/* |

### 2.4 Configuration (MODIFICARE)
| File | Modifica |
|------|----------|
| `dadude/app/config.py` | Cambiare `database_url` default da SQLite a PostgreSQL |
| `dadude/.env.example` | Aggiornare DATABASE_URL template |
| `dadude/requirements.txt` | Sostituire `aiosqlite` con `asyncpg`, aggiungere `psycopg2-binary` |

### 2.5 Migration Scripts (CREARE NUOVI)
| File | Scopo |
|------|-------|
| `dadude/migrate_db.py` | Esistente - migrazione schema SQLite |
| `dadude/migrate_backup_tables.py` | Esistente - migrazione tabelle backup |

---

## 3. Query SQL da Convertire

### 3.1 SQLite-Specific → PostgreSQL
| Pattern SQLite | Pattern PostgreSQL | File |
|----------------|-------------------|------|
| `LIKE` (case sensitive) | `ILIKE` (case insensitive) | customer_service.py, tutti i routers |
| `AUTOINCREMENT` | `SERIAL` o `IDENTITY` | database.py (se usato) |
| `sqlite:///./data/` | `postgresql://user:pass@host/db` | config.py |
| `aiosqlite` driver | `asyncpg` driver | requirements.txt |

### 3.2 Type Mapping
| SQLAlchemy Type | SQLite | PostgreSQL | Note |
|-----------------|--------|------------|------|
| `JSON` | TEXT | JSONB | PostgreSQL ha supporto nativo |
| `DateTime` | TEXT | TIMESTAMP | Native support |
| `Boolean` | INTEGER (0/1) | BOOLEAN | Native support |
| `String(8)` | VARCHAR | VARCHAR | OK |

### 3.3 Index e Constraint
Tutti gli index in `database.py`, `inventory.py`, `backup_models.py` sono compatibili.
Unica modifica: PostgreSQL supporta **full-text search** nativo - considerare per ricerche.

---

## 4. Frontend HTML da Sostituire con Vue.js

### 4.1 Templates HTML (da CONVERTIRE)
| File | Linee | Complessità | Priorità |
|------|-------|-------------|----------|
| `customer_detail.html` | 4,503 | MOLTO ALTA | 1 |
| `agents.html` | 1,443 | ALTA | 2 |
| `router_detail.html` | 1,068 | ALTA | 3 |
| `mikrotik_detail.html` | 919 | MEDIA | 4 |
| `credentials.html` | 699 | MEDIA | 5 |
| `backups.html` | 423 | MEDIA | 6 |
| `settings.html` | 422 | MEDIA | 7 |
| `discovery.html` | 363 | BASSA | 8 |
| `customers.html` | 268 | BASSA | 9 |
| `settings_import_export.html` | 256 | BASSA | 10 |
| `customer_discovery.html` | 254 | BASSA | 11 |
| `base.html` | 241 | TEMPLATE BASE | 12 |
| `dashboard.html` | 239 | BASSA | 13 |
| `settings_webhooks.html` | 186 | BASSA | 14 |
| `login.html` | 112 | BASSA | 15 |
| `alerts.html` | 99 | MOLTO BASSA | 16 |
| `devices.html` | 69 | MOLTO BASSA | 17 |

**TOTALE**: ~11,564 linee di HTML da convertire in Vue.js components

### 4.2 Funzionalità JavaScript nei Templates
- **WebSocket client** per real-time updates (agenti, scansioni)
- **AJAX calls** a API REST `/api/v1/*`
- **Charts** con Chart.js (dashboard)
- **Datatables** per liste dispositivi
- **Form validation** client-side
- **Modals** per CRUD operations

---

## 5. Dipendenze da Aggiornare

### 5.1 requirements.txt Attuale
```
fastapi>=0.104.0
uvicorn[standard]>=0.24.0
jinja2>=3.1.0
routeros-api>=0.17.0
sqlalchemy>=2.0.0
aiosqlite>=0.19.0          # → RIMUOVERE
httpx>=0.25.0
aiohttp>=3.9.0
pydantic>=2.5.0
pydantic-settings>=2.1.0
python-dotenv>=1.0.0
apscheduler>=3.10.0
pysnmp>=4.4.0
impacket>=0.11.0
paramiko>=3.3.0
cryptography>=41.0.0
websockets>=12.0
python-multipart>=0.0.6
```

### 5.2 requirements.txt v2.0 (NUOVE)
```diff
# Database - SOSTITUITO
- aiosqlite>=0.19.0
+ asyncpg>=0.29.0              # PostgreSQL async driver
+ psycopg2-binary>=2.9.9       # PostgreSQL sync (per tooling)
+ alembic>=1.13.0              # Database migrations

# Cache e Sessions
+ redis>=5.0.0                 # Redis client per cache/sessions
+ aioredis>=2.0.0              # Redis async

# (opzionale per v2.0)
+ celery>=5.3.0                # Task queue per background jobs
```

---

## 6. Piano di Implementazione

### FASE 1: Database Migration (Settimana 1)

#### Step 1.1: Setup PostgreSQL
- [ ] Aggiornare `docker-compose.yml` con servizio PostgreSQL 16
- [ ] Aggiungere servizio Redis
- [ ] Creare `docker-compose.dev.yml` per development

#### Step 1.2: Alembic Setup
- [ ] Inizializzare Alembic in `dadude/`
- [ ] Configurare `alembic.ini` per PostgreSQL
- [ ] Creare migration iniziale da modelli esistenti

#### Step 1.3: Aggiornare Database Layer
- [ ] Modificare `config.py` per PostgreSQL URL
- [ ] Aggiornare `database.py` per PostgreSQL compatibility
- [ ] Convertire query `LIKE` → `ILIKE` nei services

#### Step 1.4: Script Migrazione Dati
- [ ] Creare `scripts/migrate_sqlite_to_postgres.py`
- [ ] Testare migrazione su database di sviluppo

### FASE 2: Frontend Vue.js (Settimana 2-3)

#### Step 2.1: Setup Vue Project
- [ ] Creare progetto Vue 3 con Vite in `frontend/`
- [ ] Installare Vuetify 3
- [ ] Configurare Vue Router e Pinia

#### Step 2.2: API Service Layer
- [ ] Creare `frontend/src/services/api.js` con Axios
- [ ] Implementare WebSocket client per real-time
- [ ] Creare Pinia stores per stato applicazione

#### Step 2.3: Conversione Pagine (priorità)
1. [ ] Dashboard.vue
2. [ ] CustomersList.vue + CustomerDetail.vue
3. [ ] AgentsList.vue + AgentDetail.vue
4. [ ] DevicesInventory.vue
5. [ ] Backups.vue
6. [ ] Settings.vue

### FASE 3: Integration e Testing (Settimana 4)

#### Step 3.1: Backend API Updates
- [ ] Aggiungere CORS per Vue dev server
- [ ] Verificare tutti gli endpoint API
- [ ] Aggiungere health check migliorato

#### Step 3.2: Docker Build
- [ ] Creare `frontend/Dockerfile` multi-stage
- [ ] Aggiornare `docker-compose.yml` completo
- [ ] Testare deployment completo

#### Step 3.3: Testing
- [ ] Backend: pytest per PostgreSQL
- [ ] Frontend: Vitest per components
- [ ] Integration tests

---

## 7. Rischi e Mitigazioni

| Rischio | Impatto | Mitigazione |
|---------|---------|-------------|
| Perdita dati durante migrazione | ALTO | Backup prima della migrazione, script dry-run |
| Incompatibilità agent esistenti | ALTO | Mantenere API /api/v1 compatibile |
| Tempi di downtime | MEDIO | Testare su ambiente staging |
| Complessità conversione HTML | MEDIO | Procedere per priorità, iterativo |

---

## 8. Note di Compatibilità

### Agent Compatibility (CRITICO)
- Gli agent Docker (`dadude-agent/`) comunicano via WebSocket
- **NON modificare** il protocollo WebSocket
- **NON modificare** gli endpoint API v1 esistenti
- Aggiungere nuovi endpoint come `/api/v2/*` se necessario

### Database Migration
- PostgreSQL connection string:
  ```
  postgresql+asyncpg://user:password@localhost:5432/dadude
  ```
- Redis connection:
  ```
  redis://localhost:6379/0
  ```

---

## 9. Stima Effort

| Componente | Effort | Note |
|------------|--------|------|
| PostgreSQL setup | 2h | Docker config |
| Alembic setup | 4h | Migration config |
| Database layer update | 8h | Services + models |
| Migration script | 4h | SQLite → PostgreSQL |
| Vue.js setup | 4h | Project + config |
| Vue components (17 pages) | 40h | ~2-3h per pagina media |
| API updates | 4h | CORS, health check |
| Docker build | 4h | Multi-stage, compose |
| Testing | 8h | Backend + frontend |
| **TOTALE** | **~78h** | ~2 settimane full-time |

---

## 10. Checklist Pre-Migrazione

- [ ] Backup database SQLite esistente
- [ ] Documentare stato attuale API
- [ ] Identificare clienti/installazioni da migrare
- [ ] Preparare ambiente staging
- [ ] Comunicare downtime agli utenti

---

## 11. Prossimi Passi Immediati

1. **Aggiornare docker-compose.yml** con PostgreSQL e Redis
2. **Aggiornare requirements.txt** per asyncpg
3. **Setup Alembic** per migrations
4. **Creare frontend/** con Vue.js 3
5. **Iniziare con Dashboard.vue** come proof-of-concept

---

*Documento generato automaticamente durante l'analisi del codebase DaDude v1.x*
