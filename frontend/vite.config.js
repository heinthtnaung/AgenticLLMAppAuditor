import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// The page fetches a relative `/api/audit`, because in production Python serves
// both the page and the API from one origin. `npm run dev` is the exception --
// Vite serves the page on :5173 and knows nothing about :8000 -- so the dev
// server forwards the API to the Python one. Development only: nothing proxies
// in a built page, which is why the built page needs no CORS.
export default defineConfig({
  plugins: [react()],
  // Stable filenames, not content-hashed. Hashing exists to bust a CDN cache;
  // this page is served by our own Python process and, unusually, committed to
  // git -- where a hash would make every rebuild two additions and two orphans
  // instead of one changed file.
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/[name].js',
        chunkFileNames: 'assets/[name].js',
        assetFileNames: 'assets/[name].[ext]',
      },
    },
  },
  server: {
    proxy: { '/api': 'http://127.0.0.1:8000' },
  },
})
