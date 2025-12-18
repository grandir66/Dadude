/**
 * DaDude v2.0 - Notifications Store
 * Pinia store for managing notifications
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useNotificationStore = defineStore('notifications', () => {
  // State
  const notifications = ref([])
  const maxNotifications = 100

  // Getters
  const unreadCount = computed(() => {
    return notifications.value.filter(n => !n.read).length
  })

  const recentNotifications = computed(() => {
    return notifications.value.slice(0, 10)
  })

  // Actions
  function addNotification(notification) {
    const newNotification = {
      id: Date.now(),
      timestamp: new Date().toISOString(),
      read: false,
      ...notification
    }

    notifications.value.unshift(newNotification)

    // Keep only maxNotifications
    if (notifications.value.length > maxNotifications) {
      notifications.value = notifications.value.slice(0, maxNotifications)
    }

    return newNotification
  }

  function markAsRead(id) {
    const notification = notifications.value.find(n => n.id === id)
    if (notification) {
      notification.read = true
    }
  }

  function markAllAsRead() {
    notifications.value.forEach(n => {
      n.read = true
    })
  }

  function removeNotification(id) {
    const index = notifications.value.findIndex(n => n.id === id)
    if (index !== -1) {
      notifications.value.splice(index, 1)
    }
  }

  function clearAll() {
    notifications.value = []
  }

  return {
    // State
    notifications,
    // Getters
    unreadCount,
    recentNotifications,
    // Actions
    addNotification,
    markAsRead,
    markAllAsRead,
    removeNotification,
    clearAll,
  }
})
