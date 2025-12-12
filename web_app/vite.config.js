import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  root: 'frontend',
  build: {
    outDir: '../static/dist',
    manifest: true,
    rollupOptions: {
      input: 'main.jsx',
    },
  },
  plugins: [react()],
});
