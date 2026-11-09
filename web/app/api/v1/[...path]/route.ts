import type { NextRequest } from "next/server"
import { devPreviewEnabled } from "@/lib/dev-preview"

// Production ingress routes /api/v1 directly to Python. This loopback-only bridge
// exists solely for the isolated `npm run dev` preview, including streaming SSE.
async function forward(request: NextRequest) {
  if (!devPreviewEnabled()) return new Response(null, { status: 404 })
  const hostname = request.nextUrl.hostname
  if (
    !["localhost", "127.0.0.1", "[::1]"].includes(hostname) ||
    request.headers.get("sec-fetch-site") === "cross-site" ||
    (request.headers.has("origin") &&
      request.headers.get("origin") !== request.nextUrl.origin)
  ) {
    return new Response(null, { status: 403 })
  }
  if (request.cookies.get("skye_dev_signed_out")?.value === "true")
    return new Response(null, { status: 401 })
  const internal = new URL(process.env.SKYE_WEB_API_ORIGIN!)
  if (internal.hostname !== "127.0.0.1" || internal.protocol !== "http:")
    return new Response(null, { status: 403 })
  const headers = new Headers({
    Cookie: `__Host-skye_session=${process.env.SKYE_DEV_SESSION}`,
    "X-Skye-Internal-Token": process.env.SKYE_WEB_INTERNAL_TOKEN!,
    Origin: process.env.SKYE_WEB_ORIGIN!,
  })
  for (const name of [
    "content-type",
    "x-csrf-token",
    "x-skye-file-name",
    "last-event-id",
    "range",
  ]) {
    const value = request.headers.get(name)
    if (value) headers.set(name, value)
  }
  const upstream = await fetch(
    new URL(request.nextUrl.pathname + request.nextUrl.search, internal),
    {
      method: request.method,
      headers,
      body: ["GET", "HEAD"].includes(request.method)
        ? undefined
        : await request.arrayBuffer(),
      cache: "no-store",
      redirect: "manual",
      signal: request.signal,
    }
  )
  const responseHeaders = new Headers({
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
  })
  for (const name of [
    "content-type",
    "content-disposition",
    "accept-ranges",
    "content-range",
  ]) {
    const value = upstream.headers.get(name)
    if (value) responseHeaders.set(name, value)
  }
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  })
}

export {
  forward as GET,
  forward as POST,
  forward as PATCH,
  forward as DELETE,
  forward as HEAD,
}
