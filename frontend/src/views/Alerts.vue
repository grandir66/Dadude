<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-4">
      <h1 class="text-h4">Avvisi</h1>
      <div class="d-flex gap-2">
        <v-btn
          color="success"
          prepend-icon="mdi-check-all"
          @click="acknowledgeAll"
          :disabled="!hasUnacknowledged"
        >
          Conferma Tutti
        </v-btn>
        <v-btn color="secondary" prepend-icon="mdi-refresh" @click="loadAlerts" :loading="loading">
          Aggiorna
        </v-btn>
      </div>
    </div>

    <!-- Statistiche -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card color="error" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.critical }}</div>
            <div class="text-body-2">Critici</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="warning" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.warning }}</div>
            <div class="text-body-2">Avvisi</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="info" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.info }}</div>
            <div class="text-body-2">Info</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="success" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.acknowledged }}</div>
            <div class="text-body-2">Confermati</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Filtri -->
    <v-card class="mb-4">
      <v-card-text>
        <v-row>
          <v-col cols="12" md="3">
            <v-text-field
              v-model="search"
              label="Cerca"
              prepend-inner-icon="mdi-magnify"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-select
              v-model="filterSeverity"
              :items="severityOptions"
              label="Severità"
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
          <v-col cols="12" md="3">
            <v-select
              v-model="filterDevice"
              :items="devices"
              item-title="hostname"
              item-value="id"
              label="Dispositivo"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
          <v-col cols="12" md="2">
            <v-select
              v-model="filterType"
              :items="alertTypes"
              label="Tipo"
              clearable
              hide-details
              density="compact"
            />
          </v-col>
        </v-row>
      </v-card-text>
    </v-card>

    <!-- Lista avvisi -->
    <v-card>
      <v-data-table
        :headers="headers"
        :items="filteredAlerts"
        :search="search"
        :loading="loading"
        item-key="id"
        class="elevation-1"
      >
        <template v-slot:item.severity="{ item }">
          <v-chip :color="getSeverityColor(item.severity)" size="small">
            <v-icon start size="small">{{ getSeverityIcon(item.severity) }}</v-icon>
            {{ item.severity }}
          </v-chip>
        </template>

        <template v-slot:item.device="{ item }">
          <router-link :to="`/devices/${item.device_id}`" class="text-decoration-none">
            {{ item.device_name }}
          </router-link>
        </template>

        <template v-slot:item.message="{ item }">
          <div>
            <strong>{{ item.title }}</strong>
            <div class="text-caption text-grey">{{ item.message }}</div>
          </div>
        </template>

        <template v-slot:item.status="{ item }">
          <v-chip
            :color="item.acknowledged ? 'success' : 'grey'"
            size="small"
            variant="outlined"
          >
            {{ item.acknowledged ? 'Confermato' : 'Non confermato' }}
          </v-chip>
        </template>

        <template v-slot:item.created_at="{ item }">
          <div>
            <div>{{ formatDate(item.created_at) }}</div>
            <div class="text-caption text-grey">{{ getTimeAgo(item.created_at) }}</div>
          </div>
        </template>

        <template v-slot:item.actions="{ item }">
          <v-btn
            v-if="!item.acknowledged"
            icon="mdi-check"
            size="small"
            variant="text"
            color="success"
            @click="acknowledgeAlert(item)"
          />
          <v-btn
            icon="mdi-eye"
            size="small"
            variant="text"
            @click="viewAlert(item)"
          />
          <v-btn
            icon="mdi-delete"
            size="small"
            variant="text"
            color="error"
            @click="deleteAlert(item)"
          />
        </template>
      </v-data-table>
    </v-card>

    <!-- Dialog dettaglio avviso -->
    <v-dialog v-model="showDetailDialog" max-width="600">
      <v-card v-if="selectedAlert">
        <v-card-title class="d-flex justify-space-between align-center">
          <div class="d-flex align-center">
            <v-icon :color="getSeverityColor(selectedAlert.severity)" class="mr-2">
              {{ getSeverityIcon(selectedAlert.severity) }}
            </v-icon>
            {{ selectedAlert.title }}
          </div>
          <v-chip :color="getSeverityColor(selectedAlert.severity)" size="small">
            {{ selectedAlert.severity }}
          </v-chip>
        </v-card-title>
        <v-card-text>
          <v-list density="compact">
            <v-list-item>
              <v-list-item-title>Dispositivo</v-list-item-title>
              <v-list-item-subtitle>{{ selectedAlert.device_name }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Tipo</v-list-item-title>
              <v-list-item-subtitle>{{ selectedAlert.type }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Data</v-list-item-title>
              <v-list-item-subtitle>{{ formatDate(selectedAlert.created_at) }}</v-list-item-subtitle>
            </v-list-item>
            <v-list-item>
              <v-list-item-title>Stato</v-list-item-title>
              <v-list-item-subtitle>
                <v-chip :color="selectedAlert.acknowledged ? 'success' : 'warning'" size="small">
                  {{ selectedAlert.acknowledged ? 'Confermato' : 'Non confermato' }}
                </v-chip>
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>

          <v-divider class="my-4" />

          <h4 class="mb-2">Messaggio</h4>
          <v-alert :type="getSeverityType(selectedAlert.severity)" variant="tonal">
            {{ selectedAlert.message }}
          </v-alert>

          <div v-if="selectedAlert.details" class="mt-4">
            <h4 class="mb-2">Dettagli Tecnici</h4>
            <v-code class="d-block pa-4">
              <pre>{{ JSON.stringify(selectedAlert.details, null, 2) }}</pre>
            </v-code>
          </div>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showDetailDialog = false">Chiudi</v-btn>
          <v-btn
            v-if="!selectedAlert.acknowledged"
            color="success"
            @click="acknowledgeAlert(selectedAlert); showDetailDialog = false"
          >
            Conferma
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import api from '@/services/api'

const loading = ref(false)
const alerts = ref([])
const devices = ref([])
const search = ref('')
const filterSeverity = ref(null)
const filterStatus = ref(null)
const filterDevice = ref(null)
const filterType = ref(null)

const showDetailDialog = ref(false)
const selectedAlert = ref(null)

let refreshInterval = null

const severityOptions = ['critical', 'warning', 'info']
const statusOptions = [
  { title: 'Non confermati', value: false },
  { title: 'Confermati', value: true }
]
const alertTypes = [
  'cpu_high',
  'memory_high',
  'disk_full',
  'service_down',
  'backup_failed',
  'security',
  'offline'
]

const headers = [
  { title: 'Severità', key: 'severity', width: '120px' },
  { title: 'Dispositivo', key: 'device' },
  { title: 'Messaggio', key: 'message' },
  { title: 'Tipo', key: 'type' },
  { title: 'Stato', key: 'status' },
  { title: 'Data', key: 'created_at' },
  { title: 'Azioni', key: 'actions', sortable: false, width: '120px' }
]

const stats = computed(() => ({
  critical: alerts.value.filter(a => a.severity === 'critical' && !a.acknowledged).length,
  warning: alerts.value.filter(a => a.severity === 'warning' && !a.acknowledged).length,
  info: alerts.value.filter(a => a.severity === 'info' && !a.acknowledged).length,
  acknowledged: alerts.value.filter(a => a.acknowledged).length
}))

const hasUnacknowledged = computed(() => {
  return alerts.value.some(a => !a.acknowledged)
})

const filteredAlerts = computed(() => {
  let result = alerts.value

  if (filterSeverity.value) {
    result = result.filter(a => a.severity === filterSeverity.value)
  }
  if (filterStatus.value !== null) {
    result = result.filter(a => a.acknowledged === filterStatus.value)
  }
  if (filterDevice.value) {
    result = result.filter(a => a.device_id === filterDevice.value)
  }
  if (filterType.value) {
    result = result.filter(a => a.type === filterType.value)
  }

  return result
})

function getSeverityColor(severity) {
  const colors = { critical: 'error', warning: 'warning', info: 'info' }
  return colors[severity] || 'grey'
}

function getSeverityIcon(severity) {
  const icons = {
    critical: 'mdi-alert-circle',
    warning: 'mdi-alert',
    info: 'mdi-information'
  }
  return icons[severity] || 'mdi-bell'
}

function getSeverityType(severity) {
  const types = { critical: 'error', warning: 'warning', info: 'info' }
  return types[severity] || 'info'
}

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleString('it-IT')
}

function getTimeAgo(date) {
  if (!date) return ''
  const diff = Date.now() - new Date(date).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'Adesso'
  if (minutes < 60) return `${minutes} min fa`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours} ore fa`
  const days = Math.floor(hours / 24)
  return `${days} giorni fa`
}

function viewAlert(alert) {
  selectedAlert.value = alert
  showDetailDialog.value = true
}

async function loadAlerts() {
  loading.value = true
  try {
    const [alertsRes, devicesRes] = await Promise.all([
      api.get('/alerts'),
      api.get('/devices')
    ])
    alerts.value = alertsRes.data || []
    devices.value = devicesRes.data || []
  } catch (error) {
    console.error('Errore caricamento avvisi:', error)
  } finally {
    loading.value = false
  }
}

async function acknowledgeAlert(alert) {
  try {
    await api.post(`/alerts/${alert.id}/acknowledge`)
    alert.acknowledged = true
  } catch (error) {
    console.error('Errore conferma avviso:', error)
  }
}

async function acknowledgeAll() {
  try {
    await api.post('/alerts/acknowledge-all')
    alerts.value.forEach(a => a.acknowledged = true)
  } catch (error) {
    console.error('Errore conferma tutti:', error)
  }
}

async function deleteAlert(alert) {
  if (!confirm('Eliminare questo avviso?')) return
  try {
    await api.delete(`/alerts/${alert.id}`)
    alerts.value = alerts.value.filter(a => a.id !== alert.id)
  } catch (error) {
    console.error('Errore eliminazione:', error)
  }
}

onMounted(() => {
  loadAlerts()
  // Auto-refresh ogni 30 secondi
  refreshInterval = setInterval(loadAlerts, 30000)
})

onUnmounted(() => {
  if (refreshInterval) {
    clearInterval(refreshInterval)
  }
})
</script>
