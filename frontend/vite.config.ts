import { defineConfig } from 'vitest/config';
import { loadEnv } from 'vite';
import react from '@vitejs/plugin-react';

// https://vitejs.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '');
  const proxyTarget = env.VITE_DEV_PROXY_TARGET?.trim();

  return {
    plugins: [react()],
    optimizeDeps: {
      exclude: ['lucide-react'],
    },
    server: proxyTarget
      ? {
          proxy: {
            '/health': proxyTarget,
            '/problems': proxyTarget,
            '/volunteers': proxyTarget,
            '/volunteer': proxyTarget,
            '/volunteer-tasks': proxyTarget,
            '/recommend': proxyTarget,
            '/submit-problem': proxyTarget,
            '/transcribe': proxyTarget,
            '/analyze-image': proxyTarget,
          },
        }
      : undefined,
    test: {
      globals: true,
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
    },
  };
});
