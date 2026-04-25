import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000,
  retries: 0,
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `${path.resolve('../backend/.venv/bin/python')} ${path.resolve('../backend/start_e2e_backend.py')}`,
      port: 8011,
      timeout: 240_000,
      reuseExistingServer: true,
    },
    {
      command: 'npm run dev -- --host 127.0.0.1 --port 4173',
      port: 4173,
      timeout: 120_000,
      reuseExistingServer: true,
      env: {
        VITE_API_BASE_URL: 'http://127.0.0.1:8011',
      },
    },
  ],
});
