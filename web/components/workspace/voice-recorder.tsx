"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Mic01Icon, StopIcon } from "@hugeicons/core-free-icons"
import { InputGroupButton } from "@/components/ui/input-group"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import { useI18n } from "@/components/i18n-provider"
import type { MessageKey, MessageValues } from "@/lib/i18n"

function clock(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
}

type Translate = (key: MessageKey, values?: MessageValues) => string

function recordingError(t: Translate, description: string) {
  toast.add({
    title: t("chat.recordingFailed"),
    description,
    type: "error",
    timeout: 6000,
  })
}

export function VoiceRecorder({
  csrfToken,
  disabled,
  onReady,
}: {
  csrfToken: string
  disabled?: boolean
  onReady: (text: string) => void
}) {
  const { t } = useI18n()
  const [recording, setRecording] = React.useState(false)
  const [seconds, setSeconds] = React.useState(0)
  const [busy, setBusy] = React.useState(false)
  const recorder = React.useRef<MediaRecorder | null>(null)
  const stream = React.useRef<MediaStream | null>(null)
  const chunks = React.useRef<Blob[]>([])
  const timer = React.useRef<ReturnType<typeof setInterval> | null>(null)
  const unmounted = React.useRef(false)

  function cleanup() {
    if (timer.current) clearInterval(timer.current)
    timer.current = null
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    setRecording(false)
    setSeconds(0)
  }

  React.useEffect(() => {
    unmounted.current = false
    return () => {
      unmounted.current = true
      recorder.current?.stop()
      cleanup()
    }
  }, [])

  async function start() {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      recordingError(t, t("chat.recordingUnsupported"))
      return
    }
    try {
      const media = await navigator.mediaDevices.getUserMedia({ audio: true })
      stream.current = media
      const mime = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm"
        : MediaRecorder.isTypeSupported("audio/mp4")
          ? "audio/mp4"
          : ""
      const next = new MediaRecorder(
        media,
        mime ? { mimeType: mime } : undefined
      )
      recorder.current = next
      chunks.current = []
      next.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data)
      }
      next.onstop = () => {
        if (!unmounted.current)
          void transcribe(new Blob(chunks.current, { type: next.mimeType }))
      }
      next.start()
      setRecording(true)
      setSeconds(0)
      timer.current = setInterval(() => {
        setSeconds((value) => {
          if (value >= 299) {
            next.stop()
            cleanup()
          }
          return value + 1
        })
      }, 1000)
    } catch {
      cleanup()
      recordingError(t, t("chat.microphoneBlocked"))
    }
  }

  async function transcribe(blob: Blob) {
    cleanup()
    setBusy(true)
    const extension = blob.type.includes("mp4") ? "m4a" : "webm"
    try {
      const response = await fetch("/api/v1/audio/transcribe", {
        method: "POST",
        headers: {
          "X-CSRF-Token": csrfToken,
          "X-Skye-File-Name": `recording.${extension}`,
          "Content-Type": blob.type || "audio/webm",
        },
        body: blob,
      })
      if (!response.ok) {
        recordingError(
          t,
          response.status === 429
            ? t("chat.recordingTooMany")
            : t("chat.recordingFailedBody")
        )
        return
      }
      const data = (await response.json()) as {
        text: string
        media?: { id: string }
      }
      if (unmounted.current) return
      if (data.media?.id) {
        void fetch(`/api/v1/media/${encodeURIComponent(data.media.id)}`, {
          method: "DELETE",
          headers: { "X-CSRF-Token": csrfToken },
        }).catch(() => undefined)
      }
      const text = data.text.trim()
      if (!text) {
        toast.add({
          title: t("chat.nothingRecorded"),
          description: t("chat.nothingRecordedBody"),
          type: "info",
        })
        return
      }
      onReady(text)
    } catch {
      if (!unmounted.current)
        recordingError(t, t("chat.recordingUploadFailed"))
    } finally {
      if (!unmounted.current) setBusy(false)
    }
  }

  return recording ? (
    <InputGroupButton
      size="sm"
      variant="destructive"
      aria-label={t("chat.stopRecording")}
      onClick={() => recorder.current?.stop()}
    >
      <HugeiconsIcon icon={StopIcon} data-icon="inline-start" />
      {clock(seconds)}
    </InputGroupButton>
  ) : (
    <InputGroupButton
      size="icon-sm"
      aria-label={t("chat.recordVoice")}
      disabled={disabled || busy}
      onClick={() => void start()}
    >
      {busy ? <Spinner /> : <HugeiconsIcon icon={Mic01Icon} />}
    </InputGroupButton>
  )
}
