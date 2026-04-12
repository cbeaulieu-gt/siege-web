import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import packageJson from './package.json';

// TODO: SSG prerender for / route — deferred, see #193
// vite-plugin-react-ssg@0.2.0 requires @unhead/react which needs React >=19.2.4.
// This project is on React 18. Re-evaluate when React is upgraded.

export default defineConfig({
  plugins: [react()],
  define: {
    // Inject the package.json version at build time so SystemPage can read it
    // via import.meta.env.VITE_APP_VERSION as a fallback when the API is unavailable.
    'import.meta.env.VITE_APP_VERSION': JSON.stringify(packageJson.version),
  },
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
