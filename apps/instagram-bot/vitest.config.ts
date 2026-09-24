import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    env: {
      INSTAGRAM_MODE: 'MOCK',
      TIKTOK_MODE: 'MOCK',
      LLM_PROVIDER: 'mock',
      TELEGRAM_BOT_USERNAME: 'imovelradar_bot',
    },
  },
});
