"use client"

import type { MediaRecord } from "@/lib/contracts.generated"
import {
  defaultLocale,
  isLocale,
  translate,
  translateServerMessage,
} from "@/lib/i18n"

const MIME_EXTENSIONS: Record<string, string> = {
  "image/jpeg": "jpg",
  "image/png": "png",
  "image/webp": "webp",
  "image/gif": "gif",
  "application/pdf": "pdf",
  "application/json": "json",
  "application/zip": "zip",
  "text/csv": "csv",
  "text/html": "html",
  "text/markdown": "md",
  "text/plain": "txt",
}

function currentLocale() {
  if (typeof document === "undefined") return defaultLocale
  const lang = document.documentElement.lang
  return isLocale(lang) ? lang : defaultLocale
}

/** Clipboard images often arrive with an empty name or a generic `blob`. */
export function attachmentName(file: File, index = 0) {
  const name = file.name.trim()
  const type = file.type.split(";", 1)[0].trim().toLowerCase()
  const subtype = type.split("/")[1] ?? ""
  const extension =
    MIME_EXTENSIONS[type] ??
    (/^[a-z0-9]{1,8}$/.test(subtype) ? subtype : "bin")
  if (name && !/^blob$/i.test(name) && /\.[a-z0-9]+$/i.test(name)) return name
  const stamp = new Date()
    .toISOString()
    .slice(0, 19)
    .replace(/[-:T]/g, "")
  const base = name && !/^blob$/i.test(name) ? name : `pasted-${stamp}-${index + 1}`
  return `${base}.${extension}`
}

export function uploadMediaFile(
  file: File,
  csrfToken: string,
  onProgress?: (progress: number) => void,
  onRequest?: (request: XMLHttpRequest) => void
): Promise<MediaRecord> {
  return new Promise((resolve, reject) => {
    const locale = currentLocale()
    const request = new XMLHttpRequest()
    onRequest?.(request)
    request.open("POST", "/api/v1/media")
    request.setRequestHeader("X-CSRF-Token", csrfToken)
    request.setRequestHeader(
      "X-Skye-File-Name",
      encodeURIComponent(attachmentName(file))
    )
    request.setRequestHeader(
      "Content-Type",
      file.type || "application/octet-stream"
    )
    request.upload.onprogress = (event) => {
      if (event.lengthComputable)
        onProgress?.(Math.round((event.loaded / event.total) * 100))
    }
    request.onload = () => {
      if (request.status === 201) {
        try {
          resolve(JSON.parse(request.responseText) as MediaRecord)
        } catch {
          reject(new Error(translate(locale, "media.couldNotAttach")))
        }
        return
      }
      let message = translate(locale, "media.couldNotAttach")
      try {
        const body = JSON.parse(request.responseText) as { message?: string }
        if (body.message)
          message = translateServerMessage(locale, body.message)
      } catch {
        // Keep the localized fallback for non-JSON failures.
      }
      reject(new Error(message))
    }
    request.onerror = () =>
      reject(new Error(translate(locale, "media.uploadInterrupted")))
    request.onabort = () => {
      const error = new Error("Upload cancelled")
      error.name = "AbortError"
      reject(error)
    }
    request.send(file)
  })
}
