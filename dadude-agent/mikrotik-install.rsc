# ============================================================================
# DaDude Agent - Installazione MikroTik Container
# ============================================================================
# Copia e incolla su RouterOS - tutto automatico!
# ============================================================================

# --- CONFIGURAZIONE ---
:local serverUrl "https://dadude.domarc.it:8000"
:local deviceName [/system/identity/get name]
:local agentId ("agent-" . $deviceName)
:local agentToken ([/system/resource/get uptime] . "-" . $deviceName)

:put "=========================================="
:put "DaDude Agent Installer"
:put "=========================================="
:put ("Device: " . $deviceName)
:put ("Agent ID: " . $agentId)
:put ("Server: " . $serverUrl)
:put "=========================================="

# --- PULIZIA ---
:put "Pulizia configurazione precedente..."
:do { /container/stop [find tag~"dadude"] } on-error={}
:delay 2s
:do { /container/remove [find tag~"dadude"] } on-error={}
:do { /container/envs/remove [find name="dadude-env"] } on-error={}
:do { /container/mounts/remove [find name~"dadude"] } on-error={}
:do { /interface/veth/remove [find name="veth-dadude"] } on-error={}
:do { /interface/bridge/port/remove [find interface="veth-dadude"] } on-error={}
:do { /interface/bridge/remove [find name="br-dadude"] } on-error={}
:do { /ip/address/remove [find comment="dadude"] } on-error={}
:do { /ip/firewall/nat/remove [find comment="dadude"] } on-error={}

# --- RETE ---
:put "Configurazione rete..."
/interface/veth/add name=veth-dadude address=172.17.0.2/24 gateway=172.17.0.1
/interface/bridge/add name=br-dadude
/interface/bridge/port/add bridge=br-dadude interface=veth-dadude
/ip/address/add address=172.17.0.1/24 interface=br-dadude comment="dadude"
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 comment="dadude"

# --- STORAGE ---
:put "Preparazione storage..."
:do { /file/make-directory name="usb1/container-tmp" } on-error={}
:do { /file/make-directory name="usb1/dadude-agent" } on-error={}
/container/config/set tmpdir=usb1/container-tmp registry-url=https://ghcr.io

# --- ENVIRONMENT VARIABLES ---
:put "Configurazione environment..."
/container/envs/add list=dadude-env key=DADUDE_SERVER_URL value=$serverUrl
/container/envs/add list=dadude-env key=DADUDE_AGENT_ID value=$agentId
/container/envs/add list=dadude-env key=DADUDE_AGENT_TOKEN value=$agentToken
/container/envs/add list=dadude-env key=DADUDE_AGENT_NAME value=$deviceName

# --- CONTAINER ---
:put "Creazione container..."
/container/add \
    remote-image=ghcr.io/grandir66/dadude-agent-mikrotik:latest \
    interface=veth-dadude \
    root-dir=usb1/dadude-agent \
    envlist=dadude-env \
    dns=8.8.8.8 \
    start-on-boot=yes \
    logging=yes

:put ""
:put "=========================================="
:put "INSTALLAZIONE COMPLETATA!"
:put "=========================================="
:put ""
:put ("Agent ID: " . $agentId)
:put ("Token: " . $agentToken)
:put ("Server: " . $serverUrl)
:put ""
:put "Attendi download immagine (circa 1-2 minuti)..."
:put "Controlla stato con: /container/print"
:put ""
:put "Quando status=stopped, avvia con:"
:put "  /container/start [find tag~\"dadude\"]"
:put ""
:put "Log:"
:put "  /container/log print"
:put ""
