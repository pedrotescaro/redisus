import react from '@vitejs/plugin-react';
import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [react()],
  envDir: '../../',
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
      'next/image': fileURLToPath(new URL('./src/compat/next-image.tsx', import.meta.url)),
      'next/link': fileURLToPath(new URL('./src/compat/next-link.tsx', import.meta.url))
    }
  },
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
