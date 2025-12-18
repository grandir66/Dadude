<template>
  <div>
    <h1 class="text-h4 mb-4">Impostazioni</h1>

    <v-tabs v-model="activeTab" class="mb-4">
      <v-tab value="general">Generali</v-tab>
      <v-tab value="notifications">Notifiche</v-tab>
      <v-tab value="security">Sicurezza</v-tab>
      <v-tab value="integrations">Integrazioni</v-tab>
      <v-tab value="backup">Backup</v-tab>
      <v-tab value="system">Sistema</v-tab>
    </v-tabs>

    <v-window v-model="activeTab">
      <!-- Generali -->
      <v-window-item value="general">
        <v-card>
          <v-card-title>Impostazioni Generali</v-card-title>
          <v-card-text>
            <v-form ref="generalForm">
              <v-text-field
                v-model="settings.company_name"
                label="Nome Azienda"
                prepend-icon="mdi-domain"
              />

              <v-text-field
                v-model="settings.admin_email"
                label="Email Amministratore"
                type="email"
                prepend-icon="mdi-email"
              />

              <v-select
                v-model="settings.language"
                :items="languages"
                item-title="text"
                item-value="value"
                label="Lingua"
                prepend-icon="mdi-translate"
              />

              <v-select
                v-model="settings.timezone"
                :items="timezones"
                label="Fuso Orario"
                prepend-icon="mdi-clock-outline"
              />

              <v-select
                v-model="settings.date_format"
                :items="dateFormats"
                label="Formato Data"
                prepend-icon="mdi-calendar"
              />

              <v-switch
                v-model="settings.dark_mode"
                label="Modalità Scura"
                color="primary"
              />
            </v-form>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveSettings('general')" :loading="saving">
              Salva
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-window-item>

      <!-- Notifiche -->
      <v-window-item value="notifications">
        <v-card>
          <v-card-title>Impostazioni Notifiche</v-card-title>
          <v-card-text>
            <h4 class="mb-4">Notifiche Email</h4>
            <v-switch
              v-model="settings.email_enabled"
              label="Abilita notifiche email"
              color="primary"
            />

            <v-text-field
              v-model="settings.smtp_server"
              label="Server SMTP"
              :disabled="!settings.email_enabled"
            />

            <v-row>
              <v-col cols="6">
                <v-text-field
                  v-model="settings.smtp_port"
                  label="Porta"
                  type="number"
                  :disabled="!settings.email_enabled"
                />
              </v-col>
              <v-col cols="6">
                <v-select
                  v-model="settings.smtp_security"
                  :items="['none', 'tls', 'ssl']"
                  label="Sicurezza"
                  :disabled="!settings.email_enabled"
                />
              </v-col>
            </v-row>

            <v-text-field
              v-model="settings.smtp_user"
              label="Username SMTP"
              :disabled="!settings.email_enabled"
            />

            <v-text-field
              v-model="settings.smtp_password"
              label="Password SMTP"
              type="password"
              :disabled="!settings.email_enabled"
            />

            <v-btn
              variant="outlined"
              class="mb-4"
              @click="testEmail"
              :disabled="!settings.email_enabled"
              :loading="testingEmail"
            >
              Invia Email di Test
            </v-btn>

            <v-divider class="my-4" />

            <h4 class="mb-4">Soglie Notifiche</h4>

            <v-slider
              v-model="settings.cpu_threshold"
              label="Soglia CPU (%)"
              :min="50"
              :max="100"
              :step="5"
              thumb-label
            />

            <v-slider
              v-model="settings.memory_threshold"
              label="Soglia Memoria (%)"
              :min="50"
              :max="100"
              :step="5"
              thumb-label
            />

            <v-slider
              v-model="settings.disk_threshold"
              label="Soglia Disco (%)"
              :min="50"
              :max="100"
              :step="5"
              thumb-label
            />

            <v-divider class="my-4" />

            <h4 class="mb-4">Tipi di Notifica</h4>

            <v-checkbox
              v-model="settings.notify_device_offline"
              label="Dispositivo offline"
            />
            <v-checkbox
              v-model="settings.notify_backup_failed"
              label="Backup fallito"
            />
            <v-checkbox
              v-model="settings.notify_security_alert"
              label="Avvisi sicurezza"
            />
            <v-checkbox
              v-model="settings.notify_updates_available"
              label="Aggiornamenti disponibili"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveSettings('notifications')" :loading="saving">
              Salva
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-window-item>

      <!-- Sicurezza -->
      <v-window-item value="security">
        <v-card>
          <v-card-title>Impostazioni Sicurezza</v-card-title>
          <v-card-text>
            <h4 class="mb-4">Autenticazione</h4>

            <v-switch
              v-model="settings.two_factor_enabled"
              label="Autenticazione a due fattori"
              color="primary"
            />

            <v-slider
              v-model="settings.session_timeout"
              label="Timeout sessione (minuti)"
              :min="5"
              :max="480"
              :step="5"
              thumb-label
            />

            <v-slider
              v-model="settings.max_login_attempts"
              label="Tentativi login massimi"
              :min="3"
              :max="10"
              thumb-label
            />

            <v-divider class="my-4" />

            <h4 class="mb-4">Password Policy</h4>

            <v-slider
              v-model="settings.min_password_length"
              label="Lunghezza minima password"
              :min="6"
              :max="20"
              thumb-label
            />

            <v-checkbox
              v-model="settings.password_require_uppercase"
              label="Richiedi maiuscole"
            />
            <v-checkbox
              v-model="settings.password_require_numbers"
              label="Richiedi numeri"
            />
            <v-checkbox
              v-model="settings.password_require_symbols"
              label="Richiedi simboli"
            />

            <v-slider
              v-model="settings.password_expiry_days"
              label="Scadenza password (giorni, 0 = mai)"
              :min="0"
              :max="365"
              :step="30"
              thumb-label
            />

            <v-divider class="my-4" />

            <h4 class="mb-4">Log e Audit</h4>

            <v-switch
              v-model="settings.audit_logging"
              label="Abilita audit log"
              color="primary"
            />

            <v-slider
              v-model="settings.audit_retention_days"
              label="Retention audit log (giorni)"
              :min="30"
              :max="365"
              :step="30"
              thumb-label
              :disabled="!settings.audit_logging"
            />
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveSettings('security')" :loading="saving">
              Salva
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-window-item>

      <!-- Integrazioni -->
      <v-window-item value="integrations">
        <v-card>
          <v-card-title>Integrazioni</v-card-title>
          <v-card-text>
            <v-list>
              <v-list-item v-for="integration in integrations" :key="integration.id">
                <template v-slot:prepend>
                  <v-avatar :color="integration.enabled ? 'success' : 'grey'" size="40">
                    <v-icon>{{ integration.icon }}</v-icon>
                  </v-avatar>
                </template>
                <v-list-item-title>{{ integration.name }}</v-list-item-title>
                <v-list-item-subtitle>{{ integration.description }}</v-list-item-subtitle>
                <template v-slot:append>
                  <v-switch
                    :model-value="integration.enabled"
                    color="primary"
                    hide-details
                    @update:model-value="toggleIntegration(integration)"
                  />
                  <v-btn
                    icon="mdi-cog"
                    variant="text"
                    @click="configureIntegration(integration)"
                  />
                </template>
              </v-list-item>
            </v-list>
          </v-card-text>
        </v-card>
      </v-window-item>

      <!-- Backup -->
      <v-window-item value="backup">
        <v-card>
          <v-card-title>Backup Sistema</v-card-title>
          <v-card-text>
            <h4 class="mb-4">Backup Database</h4>

            <v-alert type="info" variant="tonal" class="mb-4">
              Ultimo backup: {{ settings.last_backup ? formatDate(settings.last_backup) : 'Mai' }}
            </v-alert>

            <v-btn
              color="primary"
              prepend-icon="mdi-database-export"
              @click="backupDatabase"
              :loading="backingUp"
              class="mb-4"
            >
              Esegui Backup Ora
            </v-btn>

            <v-divider class="my-4" />

            <h4 class="mb-4">Backup Automatico</h4>

            <v-switch
              v-model="settings.auto_backup_enabled"
              label="Abilita backup automatico"
              color="primary"
            />

            <v-select
              v-model="settings.auto_backup_frequency"
              :items="backupFrequencies"
              item-title="text"
              item-value="value"
              label="Frequenza"
              :disabled="!settings.auto_backup_enabled"
            />

            <v-text-field
              v-model="settings.auto_backup_time"
              label="Ora esecuzione"
              type="time"
              :disabled="!settings.auto_backup_enabled"
            />

            <v-slider
              v-model="settings.backup_retention"
              label="Retention backup (giorni)"
              :min="7"
              :max="90"
              thumb-label
              :disabled="!settings.auto_backup_enabled"
            />

            <v-divider class="my-4" />

            <h4 class="mb-4">Ripristino</h4>

            <v-file-input
              v-model="restoreFile"
              label="Seleziona file backup"
              accept=".sql,.backup,.zip"
              prepend-icon="mdi-database-import"
            />

            <v-btn
              color="warning"
              prepend-icon="mdi-restore"
              @click="restoreDatabase"
              :disabled="!restoreFile"
              :loading="restoring"
            >
              Ripristina Database
            </v-btn>
          </v-card-text>
          <v-card-actions>
            <v-spacer />
            <v-btn color="primary" @click="saveSettings('backup')" :loading="saving">
              Salva
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-window-item>

      <!-- Sistema -->
      <v-window-item value="system">
        <v-card>
          <v-card-title>Informazioni Sistema</v-card-title>
          <v-card-text>
            <v-list density="compact">
              <v-list-item>
                <v-list-item-title>Versione</v-list-item-title>
                <v-list-item-subtitle>DaDude v2.0.0</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>Database</v-list-item-title>
                <v-list-item-subtitle>PostgreSQL 16</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>Cache</v-list-item-title>
                <v-list-item-subtitle>Redis</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>Uptime</v-list-item-title>
                <v-list-item-subtitle>{{ systemInfo.uptime }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>Dispositivi Gestiti</v-list-item-title>
                <v-list-item-subtitle>{{ systemInfo.devices_count }}</v-list-item-subtitle>
              </v-list-item>
              <v-list-item>
                <v-list-item-title>Agent Attivi</v-list-item-title>
                <v-list-item-subtitle>{{ systemInfo.agents_count }}</v-list-item-subtitle>
              </v-list-item>
            </v-list>

            <v-divider class="my-4" />

            <h4 class="mb-4">Manutenzione</h4>

            <v-btn
              color="warning"
              prepend-icon="mdi-broom"
              @click="clearCache"
              :loading="clearingCache"
              class="mr-2 mb-2"
            >
              Pulisci Cache
            </v-btn>

            <v-btn
              color="info"
              prepend-icon="mdi-update"
              @click="checkUpdates"
              :loading="checkingUpdates"
              class="mr-2 mb-2"
            >
              Verifica Aggiornamenti
            </v-btn>

            <v-btn
              color="error"
              prepend-icon="mdi-restart"
              @click="restartServices"
              class="mb-2"
            >
              Riavvia Servizi
            </v-btn>

            <v-divider class="my-4" />

            <h4 class="mb-4">Log di Sistema</h4>

            <v-select
              v-model="logLevel"
              :items="['debug', 'info', 'warning', 'error']"
              label="Livello Log"
            />

            <v-btn
              variant="outlined"
              prepend-icon="mdi-download"
              @click="downloadLogs"
            >
              Scarica Log
            </v-btn>
          </v-card-text>
        </v-card>
      </v-window-item>
    </v-window>

    <!-- Dialog Configurazione Integrazione -->
    <v-dialog v-model="showIntegrationDialog" max-width="500">
      <v-card v-if="selectedIntegration">
        <v-card-title>Configura {{ selectedIntegration.name }}</v-card-title>
        <v-card-text>
          <v-text-field
            v-for="field in selectedIntegration.config_fields"
            :key="field.key"
            v-model="integrationConfig[field.key]"
            :label="field.label"
            :type="field.type || 'text'"
          />
        </v-card-text>
        <v-card-actions>
          <v-spacer />
          <v-btn @click="showIntegrationDialog = false">Annulla</v-btn>
          <v-btn color="primary" @click="saveIntegration">Salva</v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import api from '@/services/api'

const activeTab = ref('general')
const saving = ref(false)
const testingEmail = ref(false)
const backingUp = ref(false)
const restoring = ref(false)
const clearingCache = ref(false)
const checkingUpdates = ref(false)

const settings = ref({
  company_name: '',
  admin_email: '',
  language: 'it',
  timezone: 'Europe/Rome',
  date_format: 'DD/MM/YYYY',
  dark_mode: false,
  email_enabled: false,
  smtp_server: '',
  smtp_port: 587,
  smtp_security: 'tls',
  smtp_user: '',
  smtp_password: '',
  cpu_threshold: 80,
  memory_threshold: 85,
  disk_threshold: 90,
  notify_device_offline: true,
  notify_backup_failed: true,
  notify_security_alert: true,
  notify_updates_available: false,
  two_factor_enabled: false,
  session_timeout: 60,
  max_login_attempts: 5,
  min_password_length: 8,
  password_require_uppercase: true,
  password_require_numbers: true,
  password_require_symbols: false,
  password_expiry_days: 90,
  audit_logging: true,
  audit_retention_days: 90,
  auto_backup_enabled: true,
  auto_backup_frequency: 'daily',
  auto_backup_time: '03:00',
  backup_retention: 30,
  last_backup: null
})

const systemInfo = ref({
  uptime: 'N/A',
  devices_count: 0,
  agents_count: 0
})

const integrations = ref([
  {
    id: 1,
    name: 'Slack',
    description: 'Notifiche su canale Slack',
    icon: 'mdi-slack',
    enabled: false,
    config_fields: [
      { key: 'webhook_url', label: 'Webhook URL', type: 'text' },
      { key: 'channel', label: 'Canale', type: 'text' }
    ]
  },
  {
    id: 2,
    name: 'Microsoft Teams',
    description: 'Notifiche su Teams',
    icon: 'mdi-microsoft-teams',
    enabled: false,
    config_fields: [
      { key: 'webhook_url', label: 'Webhook URL', type: 'text' }
    ]
  },
  {
    id: 3,
    name: 'Telegram',
    description: 'Notifiche via Telegram Bot',
    icon: 'mdi-telegram',
    enabled: false,
    config_fields: [
      { key: 'bot_token', label: 'Bot Token', type: 'password' },
      { key: 'chat_id', label: 'Chat ID', type: 'text' }
    ]
  },
  {
    id: 4,
    name: 'PagerDuty',
    description: 'Integrazione incident management',
    icon: 'mdi-alarm-light',
    enabled: false,
    config_fields: [
      { key: 'api_key', label: 'API Key', type: 'password' },
      { key: 'service_key', label: 'Service Key', type: 'text' }
    ]
  }
])

const showIntegrationDialog = ref(false)
const selectedIntegration = ref(null)
const integrationConfig = ref({})

const restoreFile = ref(null)
const logLevel = ref('info')

const languages = [
  { text: 'Italiano', value: 'it' },
  { text: 'English', value: 'en' },
  { text: 'Español', value: 'es' },
  { text: 'Deutsch', value: 'de' }
]

const timezones = [
  'Europe/Rome',
  'Europe/London',
  'Europe/Paris',
  'America/New_York',
  'America/Los_Angeles',
  'Asia/Tokyo'
]

const dateFormats = [
  'DD/MM/YYYY',
  'MM/DD/YYYY',
  'YYYY-MM-DD'
]

const backupFrequencies = [
  { text: 'Giornaliero', value: 'daily' },
  { text: 'Settimanale', value: 'weekly' },
  { text: 'Mensile', value: 'monthly' }
]

function formatDate(date) {
  if (!date) return 'N/A'
  return new Date(date).toLocaleString('it-IT')
}

async function loadSettings() {
  try {
    const response = await api.get('/settings')
    settings.value = { ...settings.value, ...response.data }
  } catch (error) {
    console.error('Errore caricamento impostazioni:', error)
  }
}

async function loadSystemInfo() {
  try {
    const response = await api.get('/system/info')
    systemInfo.value = response.data
  } catch (error) {
    console.error('Errore caricamento info sistema:', error)
  }
}

async function saveSettings(section) {
  saving.value = true
  try {
    await api.put('/settings', settings.value)
  } catch (error) {
    console.error('Errore salvataggio:', error)
  } finally {
    saving.value = false
  }
}

async function testEmail() {
  testingEmail.value = true
  try {
    await api.post('/settings/test-email')
    alert('Email di test inviata!')
  } catch (error) {
    alert('Errore invio email: ' + error.message)
  } finally {
    testingEmail.value = false
  }
}

function toggleIntegration(integration) {
  integration.enabled = !integration.enabled
}

function configureIntegration(integration) {
  selectedIntegration.value = integration
  integrationConfig.value = {}
  showIntegrationDialog.value = true
}

async function saveIntegration() {
  try {
    await api.put(`/integrations/${selectedIntegration.value.id}`, integrationConfig.value)
    showIntegrationDialog.value = false
  } catch (error) {
    console.error('Errore salvataggio integrazione:', error)
  }
}

async function backupDatabase() {
  backingUp.value = true
  try {
    const response = await api.post('/system/backup')
    window.open(response.data.download_url, '_blank')
  } catch (error) {
    console.error('Errore backup:', error)
  } finally {
    backingUp.value = false
  }
}

async function restoreDatabase() {
  if (!confirm('Sei sicuro di voler ripristinare il database? Tutti i dati attuali verranno sovrascritti.')) return

  restoring.value = true
  try {
    const formData = new FormData()
    formData.append('file', restoreFile.value)
    await api.post('/system/restore', formData)
    alert('Database ripristinato con successo!')
  } catch (error) {
    alert('Errore ripristino: ' + error.message)
  } finally {
    restoring.value = false
  }
}

async function clearCache() {
  clearingCache.value = true
  try {
    await api.post('/system/clear-cache')
    alert('Cache pulita!')
  } catch (error) {
    console.error('Errore pulizia cache:', error)
  } finally {
    clearingCache.value = false
  }
}

async function checkUpdates() {
  checkingUpdates.value = true
  try {
    const response = await api.get('/system/check-updates')
    if (response.data.update_available) {
      alert(`Aggiornamento disponibile: v${response.data.latest_version}`)
    } else {
      alert('Nessun aggiornamento disponibile')
    }
  } catch (error) {
    console.error('Errore verifica aggiornamenti:', error)
  } finally {
    checkingUpdates.value = false
  }
}

async function restartServices() {
  if (!confirm('Sei sicuro di voler riavviare i servizi?')) return
  try {
    await api.post('/system/restart')
    alert('Riavvio in corso...')
  } catch (error) {
    console.error('Errore riavvio:', error)
  }
}

async function downloadLogs() {
  window.open('/api/system/logs/download', '_blank')
}

onMounted(() => {
  loadSettings()
  loadSystemInfo()
})
</script>
