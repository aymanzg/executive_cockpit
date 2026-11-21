import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// Dev: `yarn dev` proxies API calls to the local bench (site cya.local).
export default defineConfig({
  plugins: [vue()],
  base: '/assets/executive_cockpit/frontend/',
  build: {
    outDir: '../executive_cockpit/public/frontend',
    emptyOutDir: true,
    target: 'es2019',
    chunkSizeWarningLimit: 900,
  },
  server: {
    port: 8090,
    proxy: {
      '^/(api|assets|files|login|app)': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: false,
        headers: { Host: 'cya.local' },
      },
    },
  },
})
