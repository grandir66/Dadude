# ==========================================
# Fix comando container se non si avvia
# ==========================================
#
# Se il container non si avvia, prova a correggere il comando manualmente:
#
# 1. Verifica il comando attuale:
#    /container/print detail where name="dadude-agent-mikrotik"
#
# 2. Correggi il comando con le env variables (usa virgolette):
#    /container/set 0 cmd="DADUDE_SERVER_URL=https://dadude.domarc.it:8000 DADUDE_AGENT_TOKEN=mio-token-rb5009 DADUDE_AGENT_ID=agent-rb5009-test DADUDE_AGENT_NAME=RB5009\ Test DADUDE_DNS_SERVERS=192.168.4.1,8.8.8.8 PYTHONUNBUFFERED=1 python -m app.agent"
#
# 3. Avvia il container:
#    /container/start 0
#
# 4. Verifica i log:
#    /container/logs 0
#

