import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
  },
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:18090',
      '/healthz': 'http://127.0.0.1:18090',
      '/metrics': 'http://127.0.0.1:18090',
    },
  },
});
