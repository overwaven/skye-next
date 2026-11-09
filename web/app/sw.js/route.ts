// Retired SPA compatibility: old workbox workers are still registered on some
// browsers at this path. Serve a one-time self-destructing worker so they clear
// their stale app-shell caches and reload into the current Next.js client.
export const dynamic = "force-static"

const worker = `
self.addEventListener("install", () => self.skipWaiting())
self.addEventListener("activate", (event) => {
  event.waitUntil((async () => {
    const keys = await caches.keys()
    await Promise.all(keys.map((key) => caches.delete(key)))
    await self.registration.unregister()
    const clients = await self.clients.matchAll({ type: "window" })
    for (const client of clients) await client.navigate(client.url)
  })())
})
`

export function GET() {
  return new Response(worker, {
    headers: {
      "Content-Type": "application/javascript; charset=utf-8",
      "Cache-Control": "no-store",
      "Service-Worker-Allowed": "/",
    },
  })
}
