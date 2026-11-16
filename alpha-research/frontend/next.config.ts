import type { NextConfig } from "next";

// Server-side only: the browser never sees this URL. Requests to
// /api/backend/* are proxied to the FastAPI backend, so API keys and the
// backend's address stay on the server and no CORS setup is needed.
const backendUrl = (process.env.BACKEND_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const nextConfig: NextConfig = {
  // The dev server only trusts `localhost` by default; also allow the
  // loopback IP so http://127.0.0.1:3000 hydrates in development.
  allowedDevOrigins: ["127.0.0.1"],
  // Keep the dev-only Next.js badge clear of the sidebar legend.
  devIndicators: { position: "bottom-right" },
  cacheComponents: true,
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [
      {
        source: "/api/backend/:path*",
        destination: `${backendUrl}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
