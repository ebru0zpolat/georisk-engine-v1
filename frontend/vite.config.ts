import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import type { Connect, Plugin } from 'vite'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

/**
 * Serve public/<dir>/index.html at /<dir> (no trailing slash) in dev + preview.
 * After `npm run build`, scripts/flatten-clean-urls.mjs has moved these to dist/<dir>.html.
 */
function publicDirectoryIndexes(): Plugin {
  const rewriteFrom = (dir: string): Connect.NextHandleFunction => (req, _res, next) => {
    const raw = req.url?.split('?')[0] ?? ''
    if (!raw || raw === '/' || path.extname(raw)) {
      next()
      return
    }
    const query = req.url?.includes('?') ? `?${req.url.split('?')[1]}` : ''
    const page = raw.replace(/\/$/, '')
    if (fs.existsSync(path.join(__dirname, dir, raw, 'index.html'))) {
      req.url = `${raw}/index.html${query}`
    } else if (fs.existsSync(path.join(__dirname, dir, `${page}.html`))) {
      req.url = `${page}.html${query}`
    }
    next()
  }

  return {
    name: 'public-directory-indexes',
    configureServer(server) {
      server.middlewares.use(rewriteFrom('public'))
    },
    configurePreviewServer(server) {
      server.middlewares.use(rewriteFrom('dist'))
    },
  }
}

// https://vite.dev/config/
export default defineConfig({
  publicDir: 'public',
  plugins: [react(), publicDirectoryIndexes()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: {
        main: path.resolve(__dirname, 'index.html'),
        contact: path.resolve(__dirname, 'contact.html'),
      },
    },
  },
})
