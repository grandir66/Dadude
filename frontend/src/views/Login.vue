<template>
  <v-container class="fill-height">
    <v-row justify="center" align="center">
      <v-col cols="12" sm="8" md="4">
        <v-card elevation="8">
          <v-card-title class="text-center py-6">
            <h1 class="text-h4">DaDude v2.0</h1>
          </v-card-title>
          <v-card-text>
            <v-form @submit.prevent="login">
              <v-text-field
                v-model="apiKey"
                label="API Key"
                type="password"
                prepend-inner-icon="mdi-key"
                variant="outlined"
                class="mb-4"
              ></v-text-field>
              <v-btn
                type="submit"
                color="primary"
                block
                size="large"
                :loading="loading"
              >
                Login
              </v-btn>
            </v-form>
          </v-card-text>
        </v-card>
      </v-col>
    </v-row>
  </v-container>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const apiKey = ref('')
const loading = ref(false)

async function login() {
  loading.value = true
  localStorage.setItem('api_key', apiKey.value)
  router.push('/')
  loading.value = false
}
</script>
