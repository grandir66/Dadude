/**
 * DaDude v2.0 - WebSocket Service
 * Real-time communication with backend
 */
import { io } from 'socket.io-client'

class WebSocketService {
  constructor() {
    this.socket = null
    this.connected = false
    this.listeners = new Map()
    this.reconnectAttempts = 0
    this.maxReconnectAttempts = 5
  }

  /**
   * Connect to WebSocket server
   */
  connect() {
    if (this.socket?.connected) {
      return
    }

    const wsUrl = import.meta.env.VITE_WS_URL || window.location.origin

    this.socket = io(wsUrl, {
      path: '/ws/socket.io',
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionAttempts: this.maxReconnectAttempts,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
    })

    this.setupEventHandlers()
  }

  /**
   * Setup default event handlers
   */
  setupEventHandlers() {
    this.socket.on('connect', () => {
      console.log('WebSocket connected')
      this.connected = true
      this.reconnectAttempts = 0
      this.emit('connection_status', { connected: true })
    })

    this.socket.on('disconnect', (reason) => {
      console.log('WebSocket disconnected:', reason)
      this.connected = false
      this.emit('connection_status', { connected: false, reason })
    })

    this.socket.on('connect_error', (error) => {
      console.error('WebSocket connection error:', error)
      this.reconnectAttempts++
    })

    // DaDude-specific events
    this.socket.on('agent_connected', (data) => {
      this.emit('agent_connected', data)
    })

    this.socket.on('agent_disconnected', (data) => {
      this.emit('agent_disconnected', data)
    })

    this.socket.on('device_discovered', (data) => {
      this.emit('device_discovered', data)
    })

    this.socket.on('scan_started', (data) => {
      this.emit('scan_started', data)
    })

    this.socket.on('scan_progress', (data) => {
      this.emit('scan_progress', data)
    })

    this.socket.on('scan_completed', (data) => {
      this.emit('scan_completed', data)
    })

    this.socket.on('alert', (data) => {
      this.emit('alert', data)
    })

    this.socket.on('device_status', (data) => {
      this.emit('device_status', data)
    })

    this.socket.on('backup_progress', (data) => {
      this.emit('backup_progress', data)
    })

    this.socket.on('backup_completed', (data) => {
      this.emit('backup_completed', data)
    })
  }

  /**
   * Subscribe to an event
   * @param {string} event - Event name
   * @param {function} callback - Callback function
   * @returns {function} Unsubscribe function
   */
  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, new Set())
    }
    this.listeners.get(event).add(callback)

    // Return unsubscribe function
    return () => {
      this.listeners.get(event)?.delete(callback)
    }
  }

  /**
   * Emit event to listeners
   * @param {string} event - Event name
   * @param {any} data - Event data
   */
  emit(event, data) {
    const callbacks = this.listeners.get(event)
    if (callbacks) {
      callbacks.forEach(callback => {
        try {
          callback(data)
        } catch (error) {
          console.error(`Error in WebSocket listener for ${event}:`, error)
        }
      })
    }
  }

  /**
   * Send message to server
   * @param {string} event - Event name
   * @param {any} data - Data to send
   */
  send(event, data) {
    if (this.socket?.connected) {
      this.socket.emit(event, data)
    } else {
      console.warn('WebSocket not connected, cannot send:', event)
    }
  }

  /**
   * Disconnect from WebSocket server
   */
  disconnect() {
    if (this.socket) {
      this.socket.disconnect()
      this.socket = null
      this.connected = false
    }
  }

  /**
   * Check if connected
   * @returns {boolean}
   */
  isConnected() {
    return this.connected
  }
}

// Singleton instance
export const wsService = new WebSocketService()
export default wsService
