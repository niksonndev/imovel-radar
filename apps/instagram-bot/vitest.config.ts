import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    env: {
      INSTAGRAM_MODE: 'MOCK',
      TIKTOK_MODE: 'MOCK',
      WHATSAPP_ASSISTANT_URL: 'https://wa.me/5582993345293',
    },
  },
});
