"use client"

import { useEffect } from "react"

// The retired SPA registered a Workbox worker at /sw.js. Clear any surviving
// registration/cache once, then let the server-rendered client take over.
export function ServiceWorkerReset() {
  useEffect(() => {
    if (!("serviceWorker" in navigator)) return
    void (async () => {
      const registrations = await navigator.serviceWorker.getRegistrations()
      if (registrations.length === 0) return
      const controlled = Boolean(navigator.serviceWorker.controller)
      await Promise.all(
        registrations.map((registration) => registration.unregister())
      )
      if ("caches" in window) {
        const keys = await caches.keys()
        await Promise.all(keys.map((key) => caches.delete(key)))
      }
      if (controlled && sessionStorage.getItem("skye-sw-reset") !== "1") {
        sessionStorage.setItem("skye-sw-reset", "1")
        location.reload()
      }
    })()
  }, [])
  return null
}
