/**
 * DaDude v2.0 - Vuetify Plugin Configuration
 */
import 'vuetify/styles'
import { createVuetify } from 'vuetify'
import * as components from 'vuetify/components'
import * as directives from 'vuetify/directives'
import { aliases, mdi } from 'vuetify/iconsets/mdi'

// Custom theme for DaDude
const dadudeLightTheme = {
  dark: false,
  colors: {
    primary: '#1976D2',      // Blue
    secondary: '#424242',    // Grey
    accent: '#82B1FF',       // Light Blue
    error: '#FF5252',        // Red
    info: '#2196F3',         // Blue
    success: '#4CAF50',      // Green
    warning: '#FB8C00',      // Orange
    background: '#FAFAFA',
    surface: '#FFFFFF',
  }
}

const dadudeDarkTheme = {
  dark: true,
  colors: {
    primary: '#2196F3',      // Blue
    secondary: '#757575',    // Grey
    accent: '#82B1FF',       // Light Blue
    error: '#FF5252',        // Red
    info: '#2196F3',         // Blue
    success: '#4CAF50',      // Green
    warning: '#FB8C00',      // Orange
    background: '#121212',
    surface: '#1E1E1E',
  }
}

export default createVuetify({
  components,
  directives,
  icons: {
    defaultSet: 'mdi',
    aliases,
    sets: {
      mdi,
    }
  },
  theme: {
    defaultTheme: 'dadudeLightTheme',
    themes: {
      dadudeLightTheme,
      dadudeDarkTheme,
    }
  },
  defaults: {
    VCard: {
      elevation: 2,
    },
    VBtn: {
      variant: 'elevated',
    },
    VTextField: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VSelect: {
      variant: 'outlined',
      density: 'comfortable',
    },
    VDataTable: {
      hover: true,
    },
  }
})
