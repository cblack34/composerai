import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    strictPort: true,
    proxy: {
      // Compose service name. The browser stays on the Vite origin.
      '/api': 'http://backend:8000',
    },
  },
})
