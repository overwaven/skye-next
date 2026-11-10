"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import type { ResourceSnapshot } from "@/lib/contracts.generated"
import {
  defaultLocale,
  isLocale,
  translate,
  translateServerMessage,
} from "@/lib/i18n"

function currentLocale() {
  if (typeof document === "undefined") return defaultLocale
  const lang = document.documentElement.lang
  return isLocale(lang) ? lang : defaultLocale
}

export async function resourceRequest<T>(
  path: string,
  csrf: string,
  method = "GET",
  body?: unknown
): Promise<T> {
  let response: Response
  try {
    response = await fetch(`/api/v1${path}`, {
      method,
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
      headers: {
        "X-CSRF-Token": csrf,
        ...(body === undefined ? {} : { "Content-Type": "application/json" }),
      },
      ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    })
  } catch {
    throw new Error(translate(currentLocale(), "resource.unreachable"))
  }
  if (!response.ok) {
    if (response.status === 401)
      throw new Error(translate(currentLocale(), "resource.sessionExpired"))
    if (response.status === 409)
      throw new Error(translate(currentLocale(), "resource.conflict"))
    const error = await response.json().catch(() => null)
    const locale = currentLocale()
    throw new Error(
      error?.message
        ? translateServerMessage(locale, error.message)
        : translate(locale, "resource.saveFailed")
    )
  }
  return response.json()
}

export function useResourceSnapshot(
  initial: ResourceSnapshot,
  section: string
) {
  const [data, setData] = useState(initial)
  const [error, setError] = useState("")
  const refresh = useCallback(async () => {
    try {
      setData(
        await resourceRequest<ResourceSnapshot>(`/resources/${section}`, "")
      )
      setError("")
    } catch (error) {
      setError((error as Error).message)
    }
  }, [section])
  useEffect(() => {
    const tick = () => {
      if (document.visibilityState === "visible") void refresh()
    }
    window.addEventListener("focus", tick)
    const source = new EventSource("/api/v1/resources/events")
    source.addEventListener("ready", tick)
    source.addEventListener("resource.changed", tick)
    const timer = window.setInterval(tick, 15000)
    return () => {
      window.removeEventListener("focus", tick)
      window.clearInterval(timer)
      source.close()
    }
  }, [refresh])
  return { data, error, refresh }
}

export function useResourceActions(refresh: () => Promise<void>) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const [status, setStatus] = useState("")
  const errorRef = useRef<HTMLDivElement>(null)

  const perform = useCallback(
    async (work: () => Promise<void>) => {
      setBusy(true)
      setError("")
      setStatus("")
      try {
        await work()
        await refresh()
      } catch (error) {
        setError((error as Error).message)
        requestAnimationFrame(() => errorRef.current?.focus())
      } finally {
        setBusy(false)
      }
    },
    [refresh]
  )

  useEffect(() => {
    if (!status) return
    const timer = window.setTimeout(() => setStatus(""), 5000)
    return () => window.clearTimeout(timer)
  }, [status])

  return { busy, error, status, setError, setStatus, perform, errorRef }
}
