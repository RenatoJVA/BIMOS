import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      output: {
        manualChunks(id: string) {
          if (id.includes('node_modules/react')) return 'vendor';
        },
      },
    },
    target: 'es2020',
    minify: 'esbuild',
    cssMinify: 'lightningcss',
    sourcemap: false,
  },
})
