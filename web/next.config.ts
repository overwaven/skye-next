import type { NextConfig } from "next"

const nextConfig: NextConfig = {
  distDir:
    process.env.NODE_ENV === "development" &&
    process.env.SKYE_DEV_PREVIEW === "true"
      ? process.env.SKYE_DEV_DIST_DIR || ".next-preview"
      : ".next",
  devIndicators: false,
  // The production image only needs the traced standalone server, not the
  // builder's full node_modules tree.
  output: "standalone",
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Content-Security-Policy",
            value: "frame-ancestors 'none'; object-src 'none'; base-uri 'none'",
          },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "no-referrer" },
        ],
      },
    ]
  },
  // Stage 0 lab only. Production ingress will route /api/v1 directly to Python.
  async rewrites() {
    if (
      process.env.NODE_ENV !== "development" ||
      !process.env.SKYE_SPIKE_ORIGIN
    )
      return []
    const origin = new URL(process.env.SKYE_SPIKE_ORIGIN)
    if (
      !["localhost", "127.0.0.1"].includes(origin.hostname) ||
      origin.protocol !== "http:"
    ) {
      throw new Error("SKYE_SPIKE_ORIGIN must use loopback HTTP")
    }
    return [
      {
        source: "/api/v1/spike/:path*",
        destination: `${origin.origin}/api/v1/spike/:path*`,
      },
    ]
  },
}

export default nextConfig
