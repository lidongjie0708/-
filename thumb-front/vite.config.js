import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:9199',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path,
      },
      '/py-agent': {
        target: 'http://localhost:8001',
        changeOrigin: true,
        secure: false,
        rewrite: (path) => path.replace(/^\/py-agent/, '/api/agent'),
      },
    },
  },
});
