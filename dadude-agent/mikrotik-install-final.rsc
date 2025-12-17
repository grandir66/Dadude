# ============================================================================
# DaDude Agent - Installazione su MikroTik (Container Docker)
# ============================================================================
# 
# VERSIONE: 1.0.0
# TESTATO SU: RouterOS 7.x con Container package, RB5009
#
# PREREQUISITI:
#   1. Container package installato e abilitato
#      /system/device-mode/update container=yes (richiede reboot)
#   2. Disco USB montato come "usb1" (o modifica usbDisk sotto)
#   3. Connessione internet funzionante
#
# ISTRUZIONI:
#   1. Modifica i 4 valori nella sezione CONFIGURAZIONE
#   2. Copia TUTTO lo script
#   3. Incolla nella console RouterOS (SSH o Winbox Terminal)
#   4. Attendi il download dell'immagine (~2-5 minuti)
#   5. L'agent si registrerà automaticamente al server
#   6. Approva l'agent su https://dadude.domarc.it:8001/agents
#
# ============================================================================

# ============================================================================
# CONFIGURAZIONE - MODIFICA QUESTI 4 VALORI
# ============================================================================

:global dadudeAgentId "agent-NOME-SITO"
:global dadudeAgentToken "INSERISCI-TOKEN-UNIVOCO"
:global dadudeServerUrl "https://dadude.domarc.it:8000"
:global dadudeUsbDisk "usb1"

# ============================================================================
# IMMAGINE DOCKER (non modificare)
# ============================================================================

:global dadudeImage "ghcr.io/grandir66/dadude-agent-mikrotik:latest"

# ============================================================================
# 1. PULIZIA - Rimuovi installazione precedente
# ============================================================================

:put ">>> [1/7] Pulizia installazione precedente..."

:do { /container/stop [find tag~"dadude"] } on-error={}
:do { /container/remove [find tag~"dadude"] } on-error={}
:do { /interface/veth/remove [find name="veth-dadude"] } on-error={}
:do { /interface/bridge/port/remove [find interface="veth-dadude"] } on-error={}
:do { /interface/bridge/remove [find name="br-dadude"] } on-error={}
:do { /ip/address/remove [find comment="dadude-container"] } on-error={}
:do { /ip/firewall/nat/remove [find comment="dadude-nat"] } on-error={}

:delay 1s
:put "    Pulizia completata"

# ============================================================================
# 2. RETE - Crea interfacce per il container
# ============================================================================

:put ">>> [2/7] Configurazione rete container..."

# VETH: interfaccia virtuale per il container
/interface/veth/add name=veth-dadude address=172.17.0.2/24 gateway=172.17.0.1

# Bridge: collega VETH al router
/interface/bridge/add name=br-dadude
/interface/bridge/port/add bridge=br-dadude interface=veth-dadude

# IP del gateway (lato router)
/ip/address/add address=172.17.0.1/24 interface=br-dadude comment="dadude-container"

:put "    Rete configurata: 172.17.0.2 (container) <-> 172.17.0.1 (router)"

# ============================================================================
# 3. NAT - Permetti al container di accedere a internet
# ============================================================================

:put ">>> [3/7] Configurazione NAT..."

# IMPORTANTE: NON specificare out-interface (era il bug precedente)
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 comment="dadude-nat"

:put "    NAT configurato per 172.17.0.0/24"

# ============================================================================
# 4. CONTAINER CONFIG - Directory e registry
# ============================================================================

:put ">>> [4/7] Configurazione container..."

# Crea directory su USB
:do { /file/make-directory name="$dadudeUsbDisk/container-tmp" } on-error={}
:do { /file/make-directory name="$dadudeUsbDisk/dadude-agent" } on-error={}

# Configura container system
/container/config/set tmpdir="$dadudeUsbDisk/container-tmp" registry-url=https://ghcr.io

:put "    Directory: /$dadudeUsbDisk/dadude-agent"
:put "    Registry: ghcr.io"

# ============================================================================
# 5. CREA CONTAINER
# ============================================================================

:put ">>> [5/7] Creazione container..."
:put "    Immagine: $dadudeImage"
:put "    Agent ID: $dadudeAgentId"
:put "    Server: $dadudeServerUrl"

# Comando di avvio con tutte le variabili d'ambiente inline
# (evita problemi di scope delle variabili RouterOS)
:local startCmd ("sh -c 'PYTHONPATH=/app DADUDE_SERVER_URL=" . $dadudeServerUrl . " DADUDE_AGENT_TOKEN=" . $dadudeAgentToken . " DADUDE_AGENT_ID=" . $dadudeAgentId . " python -m app.agent'")

/container/add \
    remote-image=$dadudeImage \
    interface=veth-dadude \
    root-dir="$dadudeUsbDisk/dadude-agent" \
    workdir=/ \
    dns=8.8.8.8 \
    start-on-boot=yes \
    logging=yes \
    cmd=$startCmd

:put "    Container creato, download in corso..."

# ============================================================================
# 6. ATTENDI DOWNLOAD
# ============================================================================

:put ">>> [6/7] Download immagine in corso..."
:put "    Questo può richiedere 2-5 minuti..."
:put ""

# Attendi che il download completi (stato passa da extracting a stopped)
:local maxWait 300
:local waited 0
:local status ""

:while ($waited < $maxWait) do={
    :set status [/container/get [find tag~"dadude"] status]
    :if ($status = "stopped" || $status = "running") do={
        :put "    Download completato!"
        :set waited $maxWait
    } else={
        :if (($waited % 30) = 0) do={
            :put ("    Stato: " . $status . " (atteso " . $waited . "s)")
        }
        :delay 5s
        :set waited ($waited + 5)
    }
}

# ============================================================================
# 7. AVVIA CONTAINER
# ============================================================================

:put ">>> [7/7] Avvio container..."

/container/start [find tag~"dadude"]

:delay 5s

# ============================================================================
# VERIFICA FINALE
# ============================================================================

:put ""
:put "============================================================================"
:put "INSTALLAZIONE COMPLETATA"
:put "============================================================================"
:put ""

/container/print where tag~"dadude"

:put ""
:put "PROSSIMI PASSI:"
:put "  1. Verifica i log: /container/logs [find tag~\"dadude\"]"
:put "  2. L'agent si registrera' automaticamente al server"
:put "  3. Approva l'agent su: https://dadude.domarc.it:8001/agents"
:put ""
:put "COMANDI UTILI:"
:put "  /container/print                    - Stato container"
:put "  /container/logs [find tag~\"dadude\"] - Log agent"
:put "  /container/shell [find tag~\"dadude\"] - Shell nel container"
:put "  /container/stop [find tag~\"dadude\"]  - Ferma container"
:put "  /container/start [find tag~\"dadude\"] - Avvia container"
:put ""
:put "============================================================================"

