import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';
import path from 'node:path';
import fs from 'node:fs';

// Override-tree architecture.
//
// Desktop (apps/desktop/src) is the source of truth. Mobile keeps a thin
// overrides/ mirror at apps/mobile/src/overrides that shadows individual
// desktop files. The plugin below intercepts imports *before* vite alias
// resolution, computes the target's path inside desktop's tree, and returns
// the mobile override if one exists at the mirrored path.
//
// Handles both alias imports (@/..., @/app/...) and relative imports from
// inside desktop's own tree (`./sibling`), so desktop's internal sibling
// imports also respect mobile overrides — which is what re-export shims
// couldn't do.

const DESKTOP_SRC = path.resolve(__dirname, '../desktop/src');
const OVERRIDES = path.resolve(__dirname, 'src/overrides');
const RESOLVE_EXTS = ['', '.ts', '.tsx', '.js', '.jsx', '/index.ts', '/index.tsx', '/index.js'];

const overrideTree = {
  name: 'hermes-override-tree',
  enforce: 'pre' as const,
  resolveId(source: string, importer: string | undefined) {
    let candidate: string | null = null;
    if (source.startsWith('@/app/')) {
      candidate = path.join(DESKTOP_SRC, 'app', source.slice('@/app/'.length));
    } else if (source === '@/app') {
      candidate = path.join(DESKTOP_SRC, 'app');
    } else if (source.startsWith('@/')) {
      candidate = path.join(DESKTOP_SRC, source.slice(2));
    } else if (path.isAbsolute(source) && source.startsWith(DESKTOP_SRC + path.sep)) {
      // Some other plugin (vite alias) may have already resolved an `@/...`
      // import to its desktop target before we ran.
      candidate = source;
    } else if (source.startsWith('.') && importer) {
      const imp = importer.split('?')[0];
      if (!imp.startsWith(DESKTOP_SRC + path.sep) && !imp.startsWith(OVERRIDES + path.sep)) return null;
      // Imports from inside an override file: relative paths resolve against
      // the override's tree location; translate to the equivalent desktop path
      // so we apply the same override-vs-desktop logic.
      const root = imp.startsWith(OVERRIDES + path.sep) ? OVERRIDES : DESKTOP_SRC;
      const importerDir = path.dirname(imp);
      const abs = path.resolve(importerDir, source);
      const rel = path.relative(root, abs);
      candidate = path.join(DESKTOP_SRC, rel);
      if (!candidate.startsWith(DESKTOP_SRC + path.sep)) return null;
    } else {
      return null;
    }
    const relWithoutExt = path.relative(DESKTOP_SRC, candidate).replace(/\.(ts|tsx|js|jsx)$/, '');
    const overrideBase = path.join(OVERRIDES, relWithoutExt);
    for (const ext of RESOLVE_EXTS) {
      const p = overrideBase + ext;
      if (fs.existsSync(p) && fs.statSync(p).isFile()) {
        if (process.env.HERMES_RESOLVER_DEBUG) console.error(`[ot.O] ${relWithoutExt}`);
        return p;
      }
    }
    // No override. If this came from an override file's relative import, the
    // default resolver would look beside the override file and fail. Return
    // the desktop path so the bundler reads from there instead.
    if (importer?.startsWith(OVERRIDES + path.sep) && source.startsWith('.')) {
      const desktopBase = candidate.replace(/\.(ts|tsx|js|jsx)$/, '');
      for (const ext of RESOLVE_EXTS) {
        const p = desktopBase + ext;
        if (fs.existsSync(p) && fs.statSync(p).isFile()) {
          if (process.env.HERMES_RESOLVER_DEBUG) console.error(`[ot.D] ${relWithoutExt}`);
          return p;
        }
      }
    }
    return null;
  },
};

export default defineConfig({
  base: './',
  plugins: [overrideTree, react(), tailwindcss()],
  css: { postcss: { plugins: [] } },
  build: {
    minify: false,
    sourcemap: 'inline',
    rollupOptions: {
      output: {
        inlineDynamicImports: true,
      },
    },
  },
  resolve: {
    alias: [
      { find: '@/app', replacement: path.resolve(DESKTOP_SRC, 'app') },
      { find: 'react-arborist', replacement: path.resolve(__dirname, 'src/mobile-shims/react-arborist.tsx') },
      { find: 'react-shiki', replacement: path.resolve(__dirname, 'src/mobile-shims/react-shiki.tsx') },
      { find: 'use-stick-to-bottom', replacement: path.resolve(__dirname, 'src/mobile-shims/use-stick-to-bottom.tsx') },
      { find: '@hermes/shared', replacement: path.resolve(__dirname, 'src/mobile-shims/hermes-shared') },
      { find: '@', replacement: DESKTOP_SRC },
    ],
    dedupe: ['react', 'react-dom'],
  },
  server: { host: '0.0.0.0', port: 5174, strictPort: true },
});
