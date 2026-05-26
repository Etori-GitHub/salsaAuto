import { defineConfig } from 'vite';
import { resolve } from 'path';

export default defineConfig({
  root: resolve(__dirname),
  publicDir: 'web/static',
  build: {
    outDir: 'web/static/game',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        'rpg-demo': resolve(__dirname, 'src/game/rpg-demo/index.ts'),
      },
      output: {
        entryFileNames: '[name].bundle.js',
        chunkFileNames: '[name].[hash].js',
        assetFileNames: '[name].[ext]',
      },
    },
  },
  resolve: {
    alias: {
      '@gamemark': resolve(__dirname, 'src/gamemark'),
    },
  },
  server: {
    port: 3001,
    open: '/game.html',
  },
});
