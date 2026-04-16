import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  base: '/no-one-is-an-island/',
  assetsInclude: ['**/*.md'],
});
