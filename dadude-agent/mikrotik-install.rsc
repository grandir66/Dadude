# ============================================================================
# DaDude Agent - Installazione MikroTik Container
# ============================================================================
#
# ISTRUZIONI:
# 1. Cerca e sostituisci questi 2 placeholder:
#    - AGENT_TOKEN_QUI   → es: mio-token-sicuro-2024
#    - USB_DISK_QUI      → es: usb1
#
# 2. L'AGENT_ID viene generato automaticamente dal MAC del router
#    (persistente anche dopo riavvii)
#
# 3. Copia TUTTO e incolla su RouterOS
#
# ============================================================================

# Genera ID univoco persistente basato sul MAC del router
:local routerMac ""
:do {
    :set routerMac [/interface/ethernet/get [find default-name~"ether"] mac-address]
} on-error={
    :set routerMac [/system/identity/get name]
}

# Pulisci MAC (rimuovi : e -)
:local macClean ""
:local i 0
:while ($i < [:len $routerMac]) do={
    :local char [:pick $routerMac $i ($i + 1)]
    :if (($char != ":") && ($char != "-")) do={
        :set macClean ($macClean . $char)
    }
    :set i ($i + 1)
}

# Prendi ultimi 6 caratteri
:local macSuffix [:pick $macClean ([:len $macClean] - 6) [:len $macClean]]
:local agentId ("agent-mikrotik-" . $macSuffix)

:put ("Agent ID generato: " . $agentId)
:put ("MAC router: " . $routerMac)

# Pulizia completa
:do { /container/stop 0 } on-error={}
:do { /container/remove 0 } on-error={}
:do { /interface/veth/remove [find name="veth-dadude"] } on-error={}
:do { /interface/bridge/port/remove [find interface="veth-dadude"] } on-error={}
:do { /interface/bridge/remove [find name="br-dadude"] } on-error={}
:do { /ip/address/remove [find comment="dadude"] } on-error={}
:do { /ip/firewall/nat/remove [find comment="dadude"] } on-error={}

# Rete container
/interface/veth/add name=veth-dadude address=172.17.0.2/24 gateway=172.17.0.1
/interface/bridge/add name=br-dadude
/interface/bridge/port/add bridge=br-dadude interface=veth-dadude
/ip/address/add address=172.17.0.1/24 interface=br-dadude comment="dadude"
/ip/firewall/nat/add chain=srcnat action=masquerade src-address=172.17.0.0/24 comment="dadude"

# Directory container
:do { /file/make-directory name="USB_DISK_QUI/container-tmp" } on-error={}
:do { /file/make-directory name="USB_DISK_QUI/dadude-agent" } on-error={}
/container/config/set tmpdir=USB_DISK_QUI/container-tmp registry-url=https://ghcr.io

# Costruisci comando container con agent_id generato
:local cmdBase "sh -c 'PYTHONPATH=/app DADUDE_SERVER_URL=https://dadude.domarc.it:8000 DADUDE_AGENT_TOKEN=AGENT_TOKEN_QUI DADUDE_AGENT_ID="
:local cmdEnd " python -m app.agent'"
:local containerCmd ($cmdBase . $agentId . $cmdEnd)

# Crea container
/container/add remote-image=ghcr.io/grandir66/dadude-agent-mikrotik:latest interface=veth-dadude root-dir=USB_DISK_QUI/dadude-agent workdir=/ dns=8.8.8.8 start-on-boot=yes logging=yes cmd=$containerCmd

:put "Container creato con Agent ID: $agentId"
:put "Attendi download immagine..."
:delay 10s
/container/print

:put ""
:put "Quando status=stopped, avvia con: /container/start 0"
:put "Log: /container/logs 0"
:put ""
:put "Agent ID salvato: $agentId (persistente dopo riavvii)"
