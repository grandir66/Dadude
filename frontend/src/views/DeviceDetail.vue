<template>
  <div v-if="device">
    <!-- Header -->
    <div class="d-flex justify-space-between align-center mb-4">
      <div class="d-flex align-center">
        <v-btn icon="mdi-arrow-left" variant="text" @click="goBack" class="mr-2" />
        <div>
          <h1 class="text-h4">{{ device.hostname }}</h1>
          <div class="text-subtitle-1 text-grey">{{ device.ip_address }}</div>
        </div>
      </div>
      <div class="d-flex gap-2">
        <v-chip :color="getStatusColor(device.status)" size="large">
          <v-icon start>{{ getStatusIcon(device.status) }}</v-icon>
          {{ device.status }}
        </v-chip>
        <v-btn color="primary" prepend-icon="mdi-remote-desktop" :disabled="device.status !== 'online'">
          Connetti
        </v-btn>
        <v-btn color="secondary" prepend-icon="mdi-refresh" @click="loadDevice" :loading="loading">
          Aggiorna
        </v-btn>
      </div>
    </div>

    <!-- Tabs -->
    <v-tabs v-model="activeTab" class="mb-4">
      <v-tab value="overview">Panoramica</v-tab>
      <v-tab value="performance">Performance</v-tab>
      <v-tab value="software">Software</v-tab>
      <v-tab value="backups">Backup</v-tab>
      <v-tab value="alerts">Avvisi</v-tab>
      <v-tab value="commands">Comandi</v-tab>
      <v-tab value="notes">Note</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- Panoramica -->
      <v-window-item value="overview">
        <v-row>
          <v-col cols="12" md="6">
            <v-card>
              <v-card-title>Informazioni Sistema</v-card-title>
              <v-card-text>
                <v-list density="compact">
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon :icon="getOsIcon(device.os)" />
                    </template>
                    <v-list-item-title>Sistema Operativo</v-list-item-title>
                    <v-list-item-subtitle>{{ device.os }} {{ device.os_version }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-memory" />
                    </template>
                    <v-list-item-title>RAM Totale</v-list-item-title>
                    <v-list-item-subtitle>{{ formatBytes(device.total_memory) }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-harddisk" />
                    </template>
                    <v-list-item-title>Disco</v-list-item-title>
                    <v-list-item-subtitle>{{ formatBytes(device.disk_used) }} / {{ formatBytes(device.disk_total) }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-cpu-64-bit" />
                    </template>
                    <v-list-item-title>Processore</v-list-item-title>
                    <v-list-item-subtitle>{{ device.cpu_model }} ({{ device.cpu_cores }} core)</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-clock-outline" />
                    </template>
                    <v-list-item-title>Ultimo Riavvio</v-list-item-title>
                    <v-list-item-subtitle>{{ formatDate(device.last_boot) }}</v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="6">
            <v-card>
              <v-card-title>Rete</v-card-title>
              <v-card-text>
                <v-list density="compact">
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-ip-network" />
                    </template>
                    <v-list-item-title>IP Locale</v-list-item-title>
                    <v-list-item-subtitle>{{ device.ip_address }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-earth" />
                    </template>
                    <v-list-item-title>IP Pubblico</v-list-item-title>
                    <v-list-item-subtitle>{{ device.public_ip || 'N/A' }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-ethernet" />
                    </template>
                    <v-list-item-title>MAC Address</v-list-item-title>
                    <v-list-item-subtitle>{{ device.mac_address }}</v-list-item-subtitle>
                  </v-list-item>
                  <v-list-item>
                    <template v-slot:prepend>
                      <v-icon icon="mdi-domain" />
                    </template>
                    <v-list-item-title>Dominio</v-list-item-title>
                    <v-list-item-subtitle>{{ device.domain || 'Workgroup' }}</v-list-item-subtitle>
                  </v-list-item>
                </v-list>
              </v-card-text>
            </v-card>
          </v-col>

          <!-- Grafici utilizzo -->
          <v-col cols="12" md="4">
            <v-card>
              <v-card-title class="text-center">CPU</v-card-title>
              <v-card-text class="text-center">
                <v-progress-circular
                  :model-value="device.cpu_usage || 0"
                  :size="120"
                  :width="12"
                  :color="getUsageColor(device.cpu_usage)"
                >
                  <span class="text-h5">{{ device.cpu_usage || 0 }}%</span>
                </v-progress-circular>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card>
              <v-card-title class="text-center">Memoria</v-card-title>
              <v-card-text class="text-center">
                <v-progress-circular
                  :model-value="device.memory_usage || 0"
                  :size="120"
                  :width="12"
                  :color="getUsageColor(device.memory_usage)"
                >
                  <span class="text-h5">{{ device.memory_usage || 0 }}%</span>
                </v-progress-circular>
              </v-card-text>
            </v-card>
          </v-col>

          <v-col cols="12" md="4">
            <v-card>
              <v-card-title class="text-center">Disco</v-card-title>
              <v-card-text class="text-center">
                <v-progress-circular
                  :model-value="device.disk_usage || 0"
                  :size="120"
                  :width="12"
                  :color="getUsageColor(device.disk_usage)"
                >
                  <span class="text-h5">{{ device.disk_usage || 0 }}%</span>
                </v-progress-circular>
              </v-card-text>
            </v-card>
          </v-col>
        </v-row>
      </v-window-item>

      <!-- Performance -->
      <v-window-item value="performance">
        <v-card>
          <v-card-title>Storico Performance (24h)</v-card-title>
          <v-card-text>
            <div style="height: 300px;">
              <!-- Placeholder per grafico -->
              <v-alert type="info" variant="tonal">
                Grafico performance - Integrazione con Chart.js richiesta
              </v-alert>
            </div>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Software -->
      <v-window-item value="software">
        <v-card>
          <v-card-title class="d-flex justify-space-between">
            <span>Software Installato</span>
            <v-btn color="primary" size="small" prepend-icon="mdi-refresh" @click="loadSoftware">
              Scansiona
            </v-btn>
          </v-card-title>
          <v-card-text>
            <v-text-field
              v-model="softwareSearch"
              label="Cerca software"
              prepend-inner-icon="mdi-magnify"
              clearable
              hide-details
              class="mb-4"
            />
            <v-data-table
              :headers="softwareHeaders"
              :items="software"
              :search="softwareSearch"
              :loading="loadingSoftware"
              density="compact"
            >
              <template v-slot:item.version="{ item }">
                <v-chip size="small" variant="outlined">{{ item.version }}</v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Backups -->
      <v-window-item value="backups">
        <v-card>
          <v-card-title class="d-flex justify-space-between">
            <span>Cronologia Backup</span>
            <v-btn color="primary" size="small" prepend-icon="mdi-backup-restore">
              Esegui Backup
            </v-btn>
          </v-card-title>
          <v-card-text>
            <v-data-table
              :headers="backupHeaders"
              :items="backups"
              :loading="loadingBackups"
              density="compact"
            >
              <template v-slot:item.status="{ item }">
                <v-chip :color="item.status === 'success' ? 'success' : 'error'" size="small">
                  {{ item.status }}
                </v-chip>
              </template>
              <template v-slot:item.size="{ item }">
                {{ formatBytes(item.size) }}
              </template>
              <template v-slot:item.created_at="{ item }">
                {{ formatDate(item.created_at) }}
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Alerts -->
      <v-window-item value="alerts">
        <v-card>
          <v-card-title>Avvisi Recenti</v-card-title>
          <v-card-text>
            <v-list v-if="alerts.length">
              <v-list-item
                v-for="alert in alerts"
                :key="alert.id"
                :class="getAlertClass(alert.severity)"
              >
                <template v-slot:prepend>
                  <v-icon :color="getAlertColor(alert.severity)">
                    {{ getAlertIcon(alert.severity) }}
                  </v-icon>
                </template>
                <v-list-item-title>{{ alert.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ alert.message }}</v-list-item-subtitle>
                <template v-slot:append>
                  <span class="text-caption">{{ formatDate(alert.created_at) }}</span>
                </template>
              </v-list-item>
            </v-list>
            <v-alert v-else type="success" variant="tonal">
              Nessun avviso attivo
            </v-alert>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Commands -->
      <v-window-item value="commands">
        <v-card>
          <v-card-title>Esegui Comando</v-card-title>
          <v-card-text>
            <v-row>
              <v-col cols="12" md="8">
                <v-text-field
                  v-model="command"
                  label="Comando"
                  prepend-inner-icon="mdi-console"
                  @keyup.enter="executeCommand"
                />
              </v-col>
              <v-col cols="12" md="4">
                <v-btn
                  color="primary"
                  block
                  @click="executeCommand"
                  :loading="executingCommand"
                  :disabled="!command || device.status !== 'online'"
                >
                  Esegui
                </v-btn>
              </v-col>
            </v-row>

            <div v-if="commandOutput" class="terminal-output mt-4">
              <pre>{{ commandOutput }}</pre>
            </div>

            <v-divider class="my-4" />

            <h4 class="mb-2">Cronologia Comandi</h4>
            <v-data-table
              :headers="commandHeaders"
              :items="commandHistory"
              density="compact"
            >
              <template v-slot:item.status="{ item }">
                <v-chip :color="item.status === 'completed' ? 'success' : 'warning'" size="small">
                  {{ item.status }}
                </v-chip>
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Notes -->
      <v-window-item value="notes">
        <v-card>
          <v-card-title class="d-flex justify-space-between">
            <span>Note</span>
            <v-btn color="primary" size="small" prepend-icon="mdi-plus" @click="showNoteDialog = true">
              Aggiungi Nota
            </v-btn>
          </v-card-title>
          <v-card-text>
            <v-list v-if="notes.length">
              <v-list-item v-for="note in notes" :key="note.id">
                <v-list-item-title>{{ note.title }}</v-list-item-title>
                <v-list-item-subtitle>{{ note.content }}</v-list-item-subtitle>
                <template v-slot:append>
                  <span class="text-caption">{{ formatDate(note.created_at) }}</span>
                </template>
              </v-list-item>
            </v-list>
            <v-alert v-else type="info" variant="tonal">
              Nessuna nota presente
            </v-alert>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>

    <!-- Dialog Nuova Nota -->
    <v-dialog v-model="showNoteDialog" max-width="500">
      <v-card>
        <v-card-title>Nuova Nota</v-card-title>
        <v-card-text>
          <v-text-field v-model="newNote.title" label="Titolo" />
          <v-textarea v-model="newNote.content" label="Contenuto" rows="4" />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showNoteDialog = false">Annulla</v-btn>
          <v-btn color="primary" @click="saveNote">Salva</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>

  <div v-else-if="loading" class="d-flex justify-center align-center" style="height: 400px;">
    <v-progress-circular indeterminate size="64" />
  </div>

  <div v-else>
    <v-alert type="error">Dispositivo non trovato</v-alert>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import api from '@/services/api'

const route = useRoute()
const router = useRouter()

const loading = ref(false)
const device = ref(null)
const activeTab = ref('overview')

// Software
const software = ref([])
const softwareSearch = ref('')
const loadingSoftware = ref(false)
const softwareHeaders = [
  { title: 'Nome', key: 'name' },
  { title: 'Versione', key: 'version' },
  { title: 'Publisher', key: 'publisher' },
  { title: 'Installato', key: 'installed_date' }
]

// Backups
const backups = ref([])
const loadingBackups = ref(false)
const backupHeaders = [
  { title: 'Tipo', key: 'type' },
  { title: 'Stato', key: 'status' },
  { title: 'Dimensione', key: 'size' },
  { title: 'Data', key: 'created_at' }
]

// Alerts
const alerts = ref([])

// Commands
const command = ref('')
const commandOutput = ref('')
const executingCommand = ref(false)
const commandHistory = ref([])
const commandHeaders = [
  { title: 'Comando', key: 'command' },
  { title: 'Stato', key: 'status' },
  { title: 'Data', key: 'executed_at' }
]

// Notes
const notes = ref([])
const showNoteDialog = ref(false)
const newNote = ref({ title: '', content: '' })

function goBack() {
  router.push('/devices')
}

function getStatusColor(status) {
  const colors = { online: 'success', offline: 'error', warning: 'warning', maintenance: 'info' }
  return colors[status] || 'grey'
}

function getStatusIcon(status) {
  const icons = { online: 'mdi-check-circle', offline: 'mdi-close-circle', warning: 'mdi-alert', maintenance: 'mdi-wrench' }
  return icons[status] || 'mdi-help-circle'
}

function getOsIcon(os) {
  if (!os) return 'mdi-desktop-classic'
  const osLower = os.toLowerCase()
  if (osLower.includes('windows')) return 'mdi-microsoft-windows'
  if (osLower.includes('linux')) return 'mdi-linux'
  if (osLower.includes('mac')) return 'mdi-apple'
  return 'mdi-desktop-classic'
}

function getUsageColor(usage) {
  if (usage >= 90) return 'error'
  if (usage >= 70) return 'warning'
  return 'success'
}

function getAlertColor(severity) {
  const colors = { critical: 'error', warning: 'warning', info: 'info' }
  return colors[severity] || 'grey'
}

function getAlertIcon(severity) {
  const icons = { critical: 'mdi-alert-circle', warning: 'mdi-alert', info: 'mdi-information' }
  return icons[severity] || 'mdi-bell'
}

function getAlertClass(severity) {
  return severity === 'critical' ? 'bg-red-lighten-5' : ''
}

function formatBytes(bytes) {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleString('it-IT')
}

async function loadDevice() {
  loading.value = true
  try {
    const response = await api.get(`/devices/${route.params.id}`)
    device.value = response.data
  } catch (error) {
    console.error('Errore caricamento dispositivo:', error)
  } finally {
    loading.value = false
  }
}

async function loadSoftware() {
  loadingSoftware.value = true
  try {
    const response = await api.get(`/devices/${route.params.id}/software`)
    software.value = response.data || []
  } catch (error) {
    console.error('Errore caricamento software:', error)
  } finally {
    loadingSoftware.value = false
  }
}

async function executeCommand() {
  if (!command.value) return
  executingCommand.value = true
  try {
    const response = await api.post(`/devices/${route.params.id}/execute`, { command: command.value })
    commandOutput.value = response.data.output
    commandHistory.value.unshift({
      command: command.value,
      status: 'completed',
      executed_at: new Date().toISOString()
    })
    command.value = ''
  } catch (error) {
    commandOutput.value = `Errore: ${error.message}`
  } finally {
    executingCommand.value = false
  }
}

async function saveNote() {
  try {
    await api.post(`/devices/${route.params.id}/notes`, newNote.value)
    notes.value.unshift({ ...newNote.value, id: Date.now(), created_at: new Date().toISOString() })
    newNote.value = { title: '', content: '' }
    showNoteDialog.value = false
  } catch (error) {
    console.error('Errore salvataggio nota:', error)
  }
}

onMounted(() => {
  loadDevice()
})
</script>

<style scoped>
.terminal-output {
  background-color: #1e1e1e;
  color: #00ff00;
  font-family: 'Courier New', monospace;
  padding: 16px;
  min-height: 150px;
  max-height: 300px;
  overflow-y: auto;
  border-radius: 4px;
}
</style>
