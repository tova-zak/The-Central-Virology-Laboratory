import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, '.', 'VITE_')
  if (command === 'build') {
    const allowed = new Set(['VITE_API_URL', 'VITE_DEPLOYMENT_MODE'])
    if (Object.keys(env).some(name => name.startsWith('VITE_') && !allowed.has(name))) {
      throw new Error('Unexpected public environment variable; browser configuration allowlist rejected it')
    }
    const environment = env.VITE_DEPLOYMENT_MODE || 'local'
    if (!['local', 'staging', 'production'].includes(environment)) {
      throw new Error('Invalid frontend deployment environment')
    }
    if (environment !== 'local') {
      let url: URL
      try {
        url = new URL(env.VITE_API_URL || '')
      } catch {
        throw new Error('Deployed frontend requires a valid HTTPS API origin')
      }
      if (url.protocol !== 'https:' || url.hostname.includes('*') || url.username || url.password || url.search || url.hash || url.pathname !== '/') {
        throw new Error('Deployed frontend requires an exact HTTPS API origin without credentials')
      }
    }
  }
  return {
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      }
    }
  },
  }
})
