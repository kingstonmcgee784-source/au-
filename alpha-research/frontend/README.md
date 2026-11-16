# Alpha Research frontend

Next.js (App Router) + React + TypeScript + Tailwind CSS + Lucide.
See the project README one level up for setup and architecture.

```bash
npm install
npm run dev     # http://localhost:3000
npm run lint
npm run build
```

`BACKEND_URL` (server-side only, default `http://127.0.0.1:8000`) sets where
`/api/backend/*` is proxied. API keys never belong in frontend env files.
