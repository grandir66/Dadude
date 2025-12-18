<template>
  <div>
    <div class="d-flex justify-space-between align-center mb-4">
      <h1 class="text-h4">Backup</h1>
      <div class="d-flex gap-2">
        <v-btn color="primary" prepend-icon="mdi-plus" @click="showScheduleDialog = true">
          Nuova Pianificazione
        </v-btn>
        <v-btn color="secondary" prepend-icon="mdi-refresh" @click="loadData" :loading="loading">
          Aggiorna
        </v-btn>
      </div>
    </div>

    <!-- Statistiche -->
    <v-row class="mb-4">
      <v-col cols="6" md="3">
        <v-card color="success" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.successful }}</div>
            <div class="text-body-2">Completati (24h)</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="error" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.failed }}</div>
            <div class="text-body-2">Falliti (24h)</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="warning" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ stats.running }}</div>
            <div class="text-body-2">In Esecuzione</div>
          </v-card-text>
        </v-card>
      </v-col>
      <v-col cols="6" md="3">
        <v-card color="info" variant="tonal">
          <v-card-text class="text-center">
            <div class="text-h4">{{ formatBytes(stats.totalSize) }}</div>
            <div class="text-body-2">Spazio Totale</div>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Tabs -->
    <v-tabs v-model="activeTab" class="mb-4">
      <v-tab value="jobs">Job in Corso</v-tab>
      <v-tab value="history">Cronologia</v-tab>
      <v-tab value="schedules">Pianificazioni</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- Job in Corso -->
      <v-window-item value="jobs">
        <v-card>
          <v-card-text>
            <v-data-table
              :headers="jobHeaders"
              :items="runningJobs"
              :loading="loading"
            >
              <template v-slot:item.progress="{ item }">
                <v-progress-linear
                  :model-value="item.progress"
                  color="primary"
                  height="20"
                  rounded
                >
                  <template v-slot:default>
                    {{ item.progress }}%
                  </template>
                </v-progress-linear>
              </template>

              <template v-slot:item.status="{ item }">
                <v-chip :color="getJobStatusColor(item.status)" size="small">
                  <v-progress-circular
                    v-if="item.status === 'running'"
                    indeterminate
                    size="14"
                    width="2"
                    class="mr-1"
                  />
                  {{ item.status }}
                </v-chip>
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon="mdi-stop"
                  size="small"
                  variant="text"
                  color="error"
                  @click="cancelJob(item)"
                  :disabled="item.status !== 'running'"
                />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Cronologia -->
      <v-window-item value="history">
        <v-card>
          <v-card-text>
            <v-row class="mb-4">
              <v-col cols="12" md="4">
                <v-text-field
                  v-model="historySearch"
                  label="Cerca"
                  prepend-inner-icon="mdi-magnify"
                  clearable
                  hide-details
                  density="compact"
                />
              </v-col>
              <v-col cols="12" md="3">
                <v-select
                  v-model="historyStatusFilter"
                  :items="['success', 'failed', 'cancelled']"
                  label="Stato"
                  clearable
                  hide-details
                  density="compact"
                />
              </v-col>
              <v-col cols="12" md="3">
                <v-select
                  v-model="historyTypeFilter"
                  :items="['full', 'incremental', 'differential']"
                  label="Tipo"
                  clearable
                  hide-details
                  density="compact"
                />
              </v-col>
            </v-row>

            <v-data-table
              :headers="historyHeaders"
              :items="filteredHistory"
              :search="historySearch"
              :loading="loading"
            >
              <template v-slot:item.status="{ item }">
                <v-chip :color="getHistoryStatusColor(item.status)" size="small">
                  <v-icon start size="small">{{ getHistoryStatusIcon(item.status) }}</v-icon>
                  {{ item.status }}
                </v-chip>
              </template>

              <template v-slot:item.type="{ item }">
                <v-chip size="small" variant="outlined">{{ item.type }}</v-chip>
              </template>

              <template v-slot:item.size="{ item }">
                {{ formatBytes(item.size) }}
              </template>

              <template v-slot:item.duration="{ item }">
                {{ formatDuration(item.duration) }}
              </template>

              <template v-slot:item.created_at="{ item }">
                {{ formatDate(item.created_at) }}
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon="mdi-restore"
                  size="small"
                  variant="text"
                  @click="restoreBackup(item)"
                  :disabled="item.status !== 'success'"
                />
                <v-btn
                  icon="mdi-download"
                  size="small"
                  variant="text"
                  @click="downloadBackup(item)"
                  :disabled="item.status !== 'success'"
                />
                <v-btn
                  icon="mdi-delete"
                  size="small"
                  variant="text"
                  color="error"
                  @click="deleteBackup(item)"
                />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Pianificazioni -->
      <v-window-item value="schedules">
        <v-card>
          <v-card-text>
            <v-data-table
              :headers="scheduleHeaders"
              :items="schedules"
              :loading="loading"
            >
              <template v-slot:item.enabled="{ item }">
                <v-switch
                  :model-value="item.enabled"
                  color="primary"
                  hide-details
                  density="compact"
                  @update:model-value="toggleSchedule(item)"
                />
              </template>

              <template v-slot:item.type="{ item }">
                <v-chip size="small" variant="outlined">{{ item.type }}</v-chip>
              </template>

              <template v-slot:item.frequency="{ item }">
                {{ formatFrequency(item) }}
              </template>

              <template v-slot:item.next_run="{ item }">
                {{ formatDate(item.next_run) }}
              </template>

              <template v-slot:item.last_run="{ item }">
                <div v-if="item.last_run">
                  {{ formatDate(item.last_run) }}
                  <v-chip
                    :color="item.last_status === 'success' ? 'success' : 'error'"
                    size="x-small"
                    class="ml-1"
                  >
                    {{ item.last_status }}
                  </v-chip>
                </div>
                <span v-else class="text-grey">Mai eseguito</span>
              </template>

              <template v-slot:item.actions="{ item }">
                <v-btn
                  icon="mdi-play"
                  size="small"
                  variant="text"
                  color="success"
                  @click="runNow(item)"
                />
                <v-btn
                  icon="mdi-pencil"
                  size="small"
                  variant="text"
                  @click="editSchedule(item)"
                />
                <v-btn
                  icon="mdi-delete"
                  size="small"
                  variant="text"
                  color="error"
                  @click="deleteSchedule(item)"
                />
              </template>
            </v-data-table>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>

    <!-- Dialog Nuova Pianificazione -->
    <v-dialog v-model="showScheduleDialog" max-width="600">
      <v-card>
        <v-card-title>{{ editingSchedule ? 'Modifica' : 'Nuova' }} Pianificazione Backup</v-card-title>
        <v-card-text>
          <v-form ref="scheduleForm">
            <v-text-field
              v-model="scheduleFormData.name"
              label="Nome"
              :rules="[v => !!v || 'Obbligatorio']"
            />

            <v-select
              v-model="scheduleFormData.device_id"
              :items="devices"
              item-title="hostname"
              item-value="id"
              label="Dispositivo"
              :rules="[v => !!v || 'Obbligatorio']"
            />

            <v-select
              v-model="scheduleFormData.type"
              :items="['full', 'incremental', 'differential']"
              label="Tipo Backup"
              :rules="[v => !!v || 'Obbligatorio']"
            />

            <v-select
              v-model="scheduleFormData.frequency"
              :items="frequencyOptions"
              item-title="text"
              item-value="value"
              label="Frequenza"
              :rules="[v => !!v || 'Obbligatorio']"
            />

            <v-text-field
              v-model="scheduleFormData.time"
              label="Ora Esecuzione"
              type="time"
              :rules="[v => !!v || 'Obbligatorio']"
            />

            <v-text-field
              v-model="scheduleFormData.retention_days"
              label="Retention (giorni)"
              type="number"
              :rules="[v => v > 0 || 'Deve essere maggiore di 0']"
            />

            <v-text-field
              v-model="scheduleFormData.destination"
              label="Destinazione"
              placeholder="/backup/path o s3://bucket/path"
            />

            <v-switch
              v-model="scheduleFormData.compress"
              label="Comprimi backup"
              color="primary"
            />

            <v-switch
              v-model="scheduleFormData.encrypt"
              label="Cifra backup"
              color="primary"
            />
          </v-form>
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showScheduleDialog = false">Annulla</v-btn>
          <v-btn color="primary" @click="saveSchedule" :loading="saving">Salva</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>

    <!-- Dialog Conferma Restore -->
    <v-dialog v-model="showRestoreDialog" max-width="400">
      <v-card>
        <v-card-title>Conferma Ripristino</v-card-title>
        <v-card-text>
          <v-alert type="warning" variant="tonal" class="mb-4">
            Stai per ripristinare il backup del {{ formatDate(selectedBackup?.created_at) }}.
            Questa operazione sovrascriverà i dati attuali.
          </v-alert>
          <v-checkbox
            v-model="restoreConfirm"
            label="Confermo di voler procedere con il ripristino"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showRestoreDialog = false">Annulla</v-btn>
          <v-btn color="warning" @click="confirmRestore" :disabled="!restoreConfirm">
            Ripristina
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import api from '@/services/api'

const loading = ref(false)
const saving = ref(false)
const activeTab = ref('jobs')

// Jobs
const runningJobs = ref([])
const jobHeaders = [
  { title: 'Dispositivo', key: 'device_name' },
  { title: 'Tipo', key: 'type' },
  { title: 'Progresso', key: 'progress', width: '200px' },
  { title: 'Stato', key: 'status' },
  { title: 'Avviato', key: 'started_at' },
  { title: 'Azioni', key: 'actions', sortable: false, width: '80px' }
]

// History
const history = ref([])
const historySearch = ref('')
const historyStatusFilter = ref(null)
const historyTypeFilter = ref(null)
const historyHeaders = [
  { title: 'Dispositivo', key: 'device_name' },
  { title: 'Tipo', key: 'type' },
  { title: 'Stato', key: 'status' },
  { title: 'Dimensione', key: 'size' },
  { title: 'Durata', key: 'duration' },
  { title: 'Data', key: 'created_at' },
  { title: 'Azioni', key: 'actions', sortable: false, width: '120px' }
]

// Schedules
const schedules = ref([])
const devices = ref([])
const showScheduleDialog = ref(false)
const editingSchedule = ref(null)
const scheduleFormData = ref({
  name: '',
  device_id: null,
  type: 'full',
  frequency: 'daily',
  time: '02:00',
  retention_days: 30,
  destination: '',
  compress: true,
  encrypt: false
})
const scheduleHeaders = [
  { title: 'Attivo', key: 'enabled', width: '80px' },
  { title: 'Nome', key: 'name' },
  { title: 'Dispositivo', key: 'device_name' },
  { title: 'Tipo', key: 'type' },
  { title: 'Frequenza', key: 'frequency' },
  { title: 'Prossima Esecuzione', key: 'next_run' },
  { title: 'Ultima Esecuzione', key: 'last_run' },
  { title: 'Azioni', key: 'actions', sortable: false, width: '120px' }
]

const frequencyOptions = [
  { text: 'Ogni ora', value: 'hourly' },
  { text: 'Giornaliero', value: 'daily' },
  { text: 'Settimanale', value: 'weekly' },
  { text: 'Mensile', value: 'monthly' }
]

// Restore
const showRestoreDialog = ref(false)
const selectedBackup = ref(null)
const restoreConfirm = ref(false)

const stats = computed(() => ({
  successful: history.value.filter(h => h.status === 'success').length,
  failed: history.value.filter(h => h.status === 'failed').length,
  running: runningJobs.value.length,
  totalSize: history.value.reduce((sum, h) => sum + (h.size || 0), 0)
}))

const filteredHistory = computed(() => {
  let result = history.value
  if (historyStatusFilter.value) {
    result = result.filter(h => h.status === historyStatusFilter.value)
  }
  if (historyTypeFilter.value) {
    result = result.filter(h => h.type === historyTypeFilter.value)
  }
  return result
})

function getJobStatusColor(status) {
  const colors = { running: 'primary', queued: 'grey', paused: 'warning' }
  return colors[status] || 'grey'
}

function getHistoryStatusColor(status) {
  const colors = { success: 'success', failed: 'error', cancelled: 'warning' }
  return colors[status] || 'grey'
}

function getHistoryStatusIcon(status) {
  const icons = { success: 'mdi-check', failed: 'mdi-close', cancelled: 'mdi-cancel' }
  return icons[status] || 'mdi-help'
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

function formatDuration(seconds) {
  if (!seconds) return 'N/A'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}h ${m}m ${s}s`
  if (m > 0) return `${m}m ${s}s`
  return `${s}s`
}

function formatFrequency(schedule) {
  const freq = {
    hourly: 'Ogni ora',
    daily: `Giornaliero alle ${schedule.time}`,
    weekly: `Settimanale alle ${schedule.time}`,
    monthly: `Mensile alle ${schedule.time}`
  }
  return freq[schedule.frequency] || schedule.frequency
}

async function loadData() {
  loading.value = true
  try {
    const [jobsRes, historyRes, schedulesRes, devicesRes] = await Promise.all([
      api.get('/backups/jobs'),
      api.get('/backups/history'),
      api.get('/backups/schedules'),
      api.get('/devices')
    ])
    runningJobs.value = jobsRes.data || []
    history.value = historyRes.data || []
    schedules.value = schedulesRes.data || []
    devices.value = devicesRes.data || []
  } catch (error) {
    console.error('Errore caricamento dati:', error)
  } finally {
    loading.value = false
  }
}

async function cancelJob(job) {
  try {
    await api.post(`/backups/jobs/${job.id}/cancel`)
    await loadData()
  } catch (error) {
    console.error('Errore cancellazione job:', error)
  }
}

function restoreBackup(backup) {
  selectedBackup.value = backup
  restoreConfirm.value = false
  showRestoreDialog.value = true
}

async function confirmRestore() {
  try {
    await api.post(`/backups/${selectedBackup.value.id}/restore`)
    showRestoreDialog.value = false
  } catch (error) {
    console.error('Errore ripristino:', error)
  }
}

async function downloadBackup(backup) {
  window.open(`/api/backups/${backup.id}/download`, '_blank')
}

async function deleteBackup(backup) {
  if (!confirm('Eliminare questo backup?')) return
  try {
    await api.delete(`/backups/${backup.id}`)
    await loadData()
  } catch (error) {
    console.error('Errore eliminazione:', error)
  }
}

async function toggleSchedule(schedule) {
  try {
    await api.patch(`/backups/schedules/${schedule.id}`, { enabled: !schedule.enabled })
    await loadData()
  } catch (error) {
    console.error('Errore toggle schedule:', error)
  }
}

function editSchedule(schedule) {
  editingSchedule.value = schedule
  scheduleFormData.value = { ...schedule }
  showScheduleDialog.value = true
}

async function saveSchedule() {
  saving.value = true
  try {
    if (editingSchedule.value) {
      await api.put(`/backups/schedules/${editingSchedule.value.id}`, scheduleFormData.value)
    } else {
      await api.post('/backups/schedules', scheduleFormData.value)
    }
    showScheduleDialog.value = false
    editingSchedule.value = null
    await loadData()
  } catch (error) {
    console.error('Errore salvataggio:', error)
  } finally {
    saving.value = false
  }
}

async function deleteSchedule(schedule) {
  if (!confirm('Eliminare questa pianificazione?')) return
  try {
    await api.delete(`/backups/schedules/${schedule.id}`)
    await loadData()
  } catch (error) {
    console.error('Errore eliminazione:', error)
  }
}

async function runNow(schedule) {
  try {
    await api.post(`/backups/schedules/${schedule.id}/run`)
    activeTab.value = 'jobs'
    await loadData()
  } catch (error) {
    console.error('Errore esecuzione:', error)
  }
}

onMounted(() => {
  loadData()
})
</script>
