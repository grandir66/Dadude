<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-4">
      <h1 class="text-h4">Dispositivi</h1>
      <div class="d-flex gap-2">
        <v-btn color="primary" prepend-icon="mdi-refresh" @click="loadDevices" :loading="loading">
          Aggiorna
        </v-btn>
      </div>
    </div>

    <!-- Filtri -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="3">
            <v-text-field
              v-model="search"
              label="Cerca dispositivi"
              prepend-inner-icon="mdi-magnify"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-select
              v-model="filterStatus"
              :items="statusOptions"
              label="Stato"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-select
              v-model="filterCustomer"
              :items="customers"
              item-title="name"
              item-value="id"
              label="Cliente"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-select
              v-model="filterType"
              :items="deviceTypes"
              label="Tipo"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="3">
            <v-select
              v-model="filterAgent"
              :items="agents"
              item-title="name"
              item-value="id"
              label="Agent"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Statistiche rapide -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card color="success" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.online }}</div>
            <div class="text-body-2">Online</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="error" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.offline }}</div>
            <div class="text-body-2">Offline</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="warning" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.warnings }}</div>
            <div class="text-body-2">Con Avvisi</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="info" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.total }}</div>
            <div class="text-body-2">Totali</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tabella dispositivi -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredDevices"
        :loading="loading"
        :search="search"
        hover
        item-key="id"
        class="elevation-1"
      >
        <template v-slot:item.status="{ item }">
          <v-chip
            :color="getStatusColor(item.status)"
            size="small"
          >
            <v-icon start size="small">{{ getStatusIcon(item.status) }}</v-icon>
            {{ item.status }}
          </v-chip>
        </template>

        <template v-slot:item.hostname="{ item }">
          <div>
            <strong>{{ item.hostname }}</strong>
            <div class="text-caption text-grey">{{ item.ip_address }}</div>
          </div>
        </template>

        <template v-slot:item.os="{ item }">
          <div class="d-flex align-center">
            <v-icon :icon="getOsIcon(item.os)" class="mr-2" size="small" />
            <span>{{ item.os }}</span>
          </div>
        </template>

        <template v-slot:item.customer="{ item }">
          <v-chip size="small" variant="outlined">
            {{ item.customer_name }}
          </v-chip>
        </template>

        <template v-slot:item.last_seen="{ item }">
          <span :class="getLastSeenClass(item.last_seen)">
            {{ formatDate(item.last_seen) }}
          </span>
        </template>

        <template v-slot:item.cpu="{ item }">
          <v-progress-linear
            :model-value="item.cpu_usage || 0"
            :color="getUsageColor(item.cpu_usage)"
            height="20"
            rounded
          >
            <template v-slot:default>
              {{ item.cpu_usage || 0 }}%
            </template>
          </v-progress-linear>
        </template>

        <template v-slot:item.memory="{ item }">
          <v-progress-linear
            :model-value="item.memory_usage || 0"
            :color="getUsageColor(item.memory_usage)"
            height="20"
            rounded
          >
            <template v-slot:default>
              {{ item.memory_usage || 0 }}%
            </template>
          </v-progress-linear>
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn
            icon="mdi-eye"
            size="small"
            variant="text"
            @click="viewDevice(item)"
          />
          <v-btn
            icon="mdi-remote-desktop"
            size="small"
            variant="text"
            @click="remoteConnect(item)"
            :disabled="item.status !== 'online'"
          />
          <v-btn
            icon="mdi-console"
            size="small"
            variant="text"
            @click="openTerminal(item)"
            :disabled="item.status !== 'online'"
          />
        </template>
      </v-data-table>
    </v-card>

    <!-- Dialog Terminale -->
    <v-dialog v-model="terminalDialog" max-width="800">
      <v-card>
        <v-card-title class="d-flex justify-space-between">
          <span>Terminale - {{ selectedDevice?.hostname }}</span>
          <v-btn icon="mdi-close" variant="text" @click="terminalDialog = false" />
        </v-card-title>
        <v-card-text>
          <div class="terminal-output" ref="terminalOutput">
            <pre>{{ terminalContent }}</pre>
          </div>
          <v-text-field
            v-model="terminalCommand"
            label="Comando"
            @keyup.enter="sendCommand"
            prepend-inner-icon="mdi-chevron-right"
            variant="outlined"
            class="mt-2"
          />
        </v-card-text>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import api from '@/services/api'

const router = useRouter()

const loading = ref(false)
const devices = ref([])
const customers = ref([])
const agents = ref([])
const search = ref('')
const filterStatus = ref(null)
const filterCustomer = ref(null)
const filterType = ref(null)
const filterAgent = ref(null)

const terminalDialog = ref(false)
const selectedDevice = ref(null)
const terminalContent = ref('')
const terminalCommand = ref('')

const statusOptions = ['online', 'offline', 'warning', 'maintenance']
const deviceTypes = ['Workstation', 'Server', 'Laptop', 'Virtual Machine', 'Network Device']

const headers = [
  { title: 'Stato', key: 'status', width: '100px' },
  { title: 'Hostname', key: 'hostname' },
  { title: 'Sistema Operativo', key: 'os' },
  { title: 'Cliente', key: 'customer' },
  { title: 'Ultimo Contatto', key: 'last_seen' },
  { title: 'CPU', key: 'cpu', width: '120px' },
  { title: 'RAM', key: 'memory', width: '120px' },
  { title: 'Azioni', key: 'actions', sortable: false, width: '150px' }
]

const stats = computed(() => ({
  online: devices.value.filter(d => d.status === 'online').length,
  offline: devices.value.filter(d => d.status === 'offline').length,
  warnings: devices.value.filter(d => d.status === 'warning').length,
  total: devices.value.length
}))

const filteredDevices = computed(() => {
  let result = devices.value

  if (filterStatus.value) {
    result = result.filter(d => d.status === filterStatus.value)
  }
  if (filterCustomer.value) {
    result = result.filter(d => d.customer_id === filterCustomer.value)
  }
  if (filterType.value) {
    result = result.filter(d => d.device_type === filterType.value)
  }
  if (filterAgent.value) {
    result = result.filter(d => d.agent_id === filterAgent.value)
  }

  return result
})

function getStatusColor(status) {
  const colors = {
    online: 'success',
    offline: 'error',
    warning: 'warning',
    maintenance: 'info'
  }
  return colors[status] || 'grey'
}

function getStatusIcon(status) {
  const icons = {
    online: 'mdi-check-circle',
    offline: 'mdi-close-circle',
    warning: 'mdi-alert',
    maintenance: 'mdi-wrench'
  }
  return icons[status] || 'mdi-help-circle'
}

function getOsIcon(os) {
  if (!os) return 'mdi-desktop-classic'
  const osLower = os.toLowerCase()
  if (osLower.includes('windows')) return 'mdi-microsoft-windows'
  if (osLower.includes('linux') || osLower.includes('ubuntu') || osLower.includes('debian')) return 'mdi-linux'
  if (osLower.includes('mac') || osLower.includes('darwin')) return 'mdi-apple'
  return 'mdi-desktop-classic'
}

function getUsageColor(usage) {
  if (usage >= 90) return 'error'
  if (usage >= 70) return 'warning'
  return 'success'
}

function getLastSeenClass(date) {
  if (!date) return 'text-grey'
  const diff = Date.now() - new Date(date).getTime()
  const minutes = diff / 60000
  if (minutes < 5) return 'text-success'
  if (minutes < 30) return 'text-warning'
  return 'text-error'
}

function formatDate(date) {
  if (!date) return 'Mai'
  return new Date(date).toLocaleString('it-IT')
}

function viewDevice(device) {
  router.push(`/devices/${device.id}`)
}

function remoteConnect(device) {
  // Apri sessione remota
  window.open(`/remote/${device.id}`, '_blank')
}

function openTerminal(device) {
  selectedDevice.value = device
  terminalContent.value = `Connesso a ${device.hostname}\n$ `
  terminalDialog.value = true
}

async function sendCommand() {
  if (!terminalCommand.value || !selectedDevice.value) return

  terminalContent.value += terminalCommand.value + '\n'

  try {
    const response = await api.post(`/devices/${selectedDevice.value.id}/execute`, {
      command: terminalCommand.value
    })
    terminalContent.value += response.data.output + '\n$ '
  } catch (error) {
    terminalContent.value += `Errore: ${error.message}\n$ `
  }

  terminalCommand.value = ''
}

async function loadDevices() {
  loading.value = true
  try {
    const response = await api.get('/devices')
    devices.value = response.data || []
  } catch (error) {
    console.error('Errore caricamento dispositivi:', error)
  } finally {
    loading.value = false
  }
}

async function loadCustomers() {
  try {
    const response = await api.get('/customers')
    customers.value = response.data || []
  } catch (error) {
    console.error('Errore caricamento clienti:', error)
  }
}

async function loadAgents() {
  try {
    const response = await api.get('/agents')
    agents.value = response.data || []
  } catch (error) {
    console.error('Errore caricamento agent:', error)
  }
}

onMounted(() => {
  loadDevices()
  loadCustomers()
  loadAgents()
})
</script>

<style scoped>
.terminal-output {
  background-color: #1e1e1e;
  color: #00ff00;
  font-family: 'Courier New', monospace;
  padding: 16px;
  min-height: 300px;
  max-height: 400px;
  overflow-y: auto;
  border-radius: 4px;
}
</style>
