import react from '@vitejs/plugin-react';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api/clinical': {
        target: process.env.CLINICAL_API_URL || 'http://127.0.0.1:5000/api/v1',
        changeOrigin: true,
        rewrite: path => path.replace(/^\/api\/clinical/, '')
      }
    }
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: './src/tests/setup.ts',
    css: true
  }
});
