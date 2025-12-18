/**
 * DaDude v2.0 - WebSocket Store
 * Pinia store for WebSocket state management
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import wsService from '@/services/websocket'

export const useWebSocketStore = defineStore('websocket', () => {
  // State
  const connected = ref(false)
  const reconnecting = ref(false)
  const lastError = ref(null)

  // Getters
  const isConnected = computed(() => connected.value)

  // Actions
  function connect() {
    wsService.connect()

    wsService.on('connection_status', (status) => {
      connected.value = status.connected
      if (!status.connected && status.reason) {
        lastError.value = status.reason
      }
    })
  }

  function disconnect() {
    wsService.disconnect()
    connected.value = false
  }

  function subscribe(event, callback) {
    return wsService.on(event, callback)
  }

  function send(event, data) {
    wsService.send(event, data)
  }

  // Auto-connect on store creation
  connect()

  return {
    // State
    connected,
    reconnecting,
    lastError,
    // Getters
    isConnected,
    // Actions
    connect,
    disconnect,
    subscribe,
    send,
  }
})
