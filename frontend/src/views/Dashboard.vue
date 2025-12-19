<template>
  <div>
    <!-- Stats Cards -->
    <v-row>
      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-item>
            <template v-slot:prepend>
              <v-avatar color="primary" size="48">
                <v-icon icon="mdi-domain"></v-icon>
              </v-avatar>
            </template>
            <v-card-title>{{ stats.customers }}</v-card-title>
            <v-card-subtitle>Customers</v-card-subtitle>
          </v-card-item>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-item>
            <template v-slot:prepend>
              <v-avatar color="success" size="48">
                <v-icon icon="mdi-server-network"></v-icon>
              </v-avatar>
            </template>
            <v-card-title>{{ stats.agentsOnline }} / {{ stats.agentsTotal }}</v-card-title>
            <v-card-subtitle>Agents Online</v-card-subtitle>
          </v-card-item>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-item>
            <template v-slot:prepend>
              <v-avatar color="info" size="48">
                <v-icon icon="mdi-devices"></v-icon>
              </v-avatar>
            </template>
            <v-card-title>{{ stats.devices }}</v-card-title>
            <v-card-subtitle>Devices</v-card-subtitle>
          </v-card-item>
        </v-card>
      </v-col>

      <v-col cols="12" sm="6" md="3">
        <v-card>
          <v-card-item>
            <template v-slot:prepend>
              <v-avatar color="warning" size="48">
                <v-icon icon="mdi-bell-alert"></v-icon>
              </v-avatar>
            </template>
            <v-card-title>{{ stats.activeAlerts }}</v-card-title>
            <v-card-subtitle>Active Alerts</v-card-subtitle>
          </v-card-item>
        </v-card>
      </v-col>
    </v-row>

    <!-- Charts Row -->
    <v-row class="mt-4">
      <v-col cols="12" md="8">
        <v-card>
          <v-card-title>
            <v-icon icon="mdi-chart-line" class="mr-2"></v-icon>
            Device Status History
          </v-card-title>
          <v-card-text>
            <Line
              :data="chartData"
              :options="chartOptions"
              style="height: 300px"
            />
          </v-card-text>
        </v-card>
      </v-col>

      <v-col cols="12" md="4">
        <v-card>
          <v-card-title>
            <v-icon icon="mdi-chart-donut" class="mr-2"></v-icon>
            Device Types
          </v-card-title>
          <v-card-text>
            <Doughnut
              :data="deviceTypeData"
              :options="doughnutOptions"
              style="height: 300px"
            />
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>

    <!-- Recent Activity Row -->
    <v-row class="mt-4">
      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon icon="mdi-bell" class="mr-2"></v-icon>
            Recent Alerts
          </v-card-title>
          <v-list lines="two">
            <v-list-item
              v-for="alert in recentAlerts"
              :key="alert.id"
              :prepend-icon="getAlertIcon(alert.severity)"
              :prepend-icon-color="getAlertColor(alert.severity)"
            >
              <v-list-item-title>{{ alert.device_name || 'Unknown Device' }}</v-list-item-title>
              <v-list-item-subtitle>{{ alert.message }}</v-list-item-subtitle>
              <template v-slot:append>
                <span class="text-caption">{{ formatTime(alert.created_at) }}</span>
              </template>
            </v-list-item>
            <v-list-item v-if="recentAlerts.length === 0">
              <v-list-item-title class="text-center text-grey">No recent alerts</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>

      <v-col cols="12" md="6">
        <v-card>
          <v-card-title>
            <v-icon icon="mdi-server-network" class="mr-2"></v-icon>
            Agent Status
          </v-card-title>
          <v-list lines="two">
            <v-list-item
              v-for="agent in agents"
              :key="agent.id"
              :to="`/agents/${agent.id}`"
            >
              <template v-slot:prepend>
                <v-avatar :color="agent.status === 'online' ? 'success' : 'error'" size="40">
                  <v-icon icon="mdi-server" color="white"></v-icon>
                </v-avatar>
              </template>
              <v-list-item-title>{{ agent.name }}</v-list-item-title>
              <v-list-item-subtitle>{{ agent.address }}</v-list-item-subtitle>
              <template v-slot:append>
                <v-chip
                  :color="agent.status === 'online' ? 'success' : 'error'"
                  size="small"
                  variant="tonal"
                >
                  {{ agent.status }}
                </v-chip>
              </template>
            </v-list-item>
            <v-list-item v-if="agents.length === 0">
              <v-list-item-title class="text-center text-grey">No agents configured</v-list-item-title>
            </v-list-item>
          </v-list>
        </v-card>
      </v-col>
    </v-row>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { Line, Doughnut } from 'vue-chartjs'
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
} from 'chart.js'
import { format, parseISO } from 'date-fns'
import { dashboardApi, agentsApi, alertsApi } from '@/services/api'
import { useWebSocketStore } from '@/stores/websocket'

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  Filler
)

const wsStore = useWebSocketStore()

// State
const loading = ref(true)
const stats = ref({
  customers: 0,
  agentsOnline: 0,
  agentsTotal: 0,
  devices: 0,
  activeAlerts: 0
})
const recentAlerts = ref([])
const agents = ref([])

// Chart data
const chartData = ref({
  labels: [],
  datasets: [{
    label: 'Online Devices',
    data: [],
    fill: true,
    borderColor: '#4CAF50',
    backgroundColor: 'rgba(76, 175, 80, 0.1)',
    tension: 0.4
  }]
})

const deviceTypeData = ref({
  labels: ['MikroTik', 'Windows', 'Linux', 'Network', 'Other'],
  datasets: [{
    data: [45, 25, 15, 10, 5],
    backgroundColor: [
      '#1976D2',
      '#00BCD4',
      '#FF9800',
      '#9C27B0',
      '#757575'
    ]
  }]
})

// Chart options
const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false
    }
  },
  scales: {
    y: {
      beginAtZero: true
    }
  }
}

const doughnutOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      position: 'bottom'
    }
  }
}

// Methods
function getAlertIcon(severity) {
  switch (severity) {
    case 'critical': return 'mdi-alert-circle'
    case 'warning': return 'mdi-alert'
    default: return 'mdi-information'
  }
}

function getAlertColor(severity) {
  switch (severity) {
    case 'critical': return 'error'
    case 'warning': return 'warning'
    default: return 'info'
  }
}

function formatTime(timestamp) {
  if (!timestamp) return ''
  try {
    return format(parseISO(timestamp), 'HH:mm')
  } catch {
    return timestamp
  }
}

async function loadDashboardData() {
  try {
    loading.value = true

    // Load stats
    const statsData = await dashboardApi.getStats()
    stats.value = {
      customers: statsData.customers || 0,
      agentsOnline: statsData.agents_online || 0,
      agentsTotal: statsData.agents_total || 0,
      devices: statsData.devices || 0,
      activeAlerts: statsData.active_alerts || 0
    }

    // Load recent alerts
    const alertsData = await alertsApi.getAll({ limit: 5 })
    recentAlerts.value = alertsData.alerts || alertsData.items || alertsData || []

    // Load agents
    const agentsData = await agentsApi.getAll()
    agents.value = agentsData.agents || agentsData.items || agentsData || []

    // Update device type chart with actual data if available
    if (statsData.device_types) {
      const types = statsData.device_types
      deviceTypeData.value = {
        labels: Object.keys(types),
        datasets: [{
          data: Object.values(types),
          backgroundColor: ['#1976D2', '#00BCD4', '#FF9800', '#9C27B0', '#757575', '#4CAF50', '#F44336']
        }]
      }
    }

  } catch (error) {
    console.error('Error loading dashboard data:', error)
  } finally {
    loading.value = false
  }
}

// WebSocket subscriptions
onMounted(() => {
  loadDashboardData()

  // Subscribe to real-time updates
  wsStore.subscribe('agent_connected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) {
      agent.status = 'online'
    }
    stats.value.agentsOnline++
  })

  wsStore.subscribe('agent_disconnected', (data) => {
    const agent = agents.value.find(a => a.id === data.agent_id)
    if (agent) {
      agent.status = 'offline'
    }
    stats.value.agentsOnline = Math.max(0, stats.value.agentsOnline - 1)
  })

  wsStore.subscribe('alert', (data) => {
    recentAlerts.value.unshift(data)
    recentAlerts.value = recentAlerts.value.slice(0, 5)
    stats.value.activeAlerts++
  })
})
</script>
