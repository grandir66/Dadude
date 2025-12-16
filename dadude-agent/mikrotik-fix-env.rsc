# ==========================================
# Fix Environment Variables per DaDude Agent
# Esegui questo script DOPO aver creato il container
# ==========================================

# Rimuovi env esistente
:do {
    /container/envs/remove [find name="dadude-env"]
} on-error={}

# Crea environment variables una alla volta
# NOTA: Esegui questi comandi uno alla volta se non funzionano insieme

/container/envs/add name=dadude-env key=DADUDE_SERVER_URL value=https://dadude.domarc.it:8000
/container/envs/add name=dadude-env key=DADUDE_AGENT_TOKEN value=mio-token-rb5009
/container/envs/add name=dadude-env key=DADUDE_AGENT_ID value=agent-rb5009-test
/container/envs/add name=dadude-env key=DADUDE_AGENT_NAME value=RB5009\ Test
/container/envs/add name=dadude-env key=DADUDE_DNS_SERVERS value=192.168.4.1,8.8.8.8
/container/envs/add name=dadude-env key=PYTHONUNBUFFERED value=1

# Aggiorna il container per usare le env
/container/set 0 envlist=dadude-env

# Avvia il container
/container/start 0

# Verifica
:delay 2s
/container/print
:put ""
:put "Per vedere i log:"
:put "  /container/logs 0"

