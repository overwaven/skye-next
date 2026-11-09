"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Mic01Icon, Square01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import { InputGroupButton } from "@/components/ui/input-group"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldLabel } from "@/components/ui/field"
import { Textarea } from "@/components/ui/textarea"
import { Spinner } from "@/components/ui/spinner"
import type { MediaRecord } from "@/lib/contracts.generated"

function clock(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, "0")}`
}

export function VoiceRecorder({
  csrfToken,
  disabled,
  onReady,
}: {
  csrfToken: string
  disabled?: boolean
  onReady: (text: string, media: MediaRecord) => void
}) {
  const [recording, setRecording] = React.useState(false)
  const [seconds, setSeconds] = React.useState(0)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState("")
  const [review, setReview] = React.useState<{
    text: string
    media: MediaRecord
    url: string
  } | null>(null)
  const recorder = React.useRef<MediaRecorder | null>(null)
  const stream = React.useRef<MediaStream | null>(null)
  const chunks = React.useRef<Blob[]>([])
  const timer = React.useRef<ReturnType<typeof setInterval> | null>(null)

  function cleanup() {
    if (timer.current) clearInterval(timer.current)
    timer.current = null
    stream.current?.getTracks().forEach((track) => track.stop())
    stream.current = null
    setRecording(false)
    setSeconds(0)
  }

  React.useEffect(() => {
    return () => {
      recorder.current?.stop()
      cleanup()
    }
  }, [])

  async function start() {
    setError("")
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      setError("Recording is not supported in this browser.")
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
      setError("Microphone access is blocked. Allow it or type instead.")
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
        setError(
          response.status === 429
            ? "Too many recordings. Wait a minute."
            : "That recording could not be transcribed. Try again."
        )
        return
      }
      const data = (await response.json()) as {
        text: string
        media: MediaRecord
      }
      setReview({
        text: data.text,
        media: data.media,
        url: URL.createObjectURL(blob),
      })
    } catch {
      setError("The recording could not be uploaded. Try again.")
    } finally {
      setBusy(false)
    }
  }

  function discard() {
    if (review) URL.revokeObjectURL(review.url)
    setReview(null)
  }

  return (
    <>
      {recording ? (
        <InputGroupButton
          size="sm"
          variant="destructive"
          aria-label="Stop recording"
          onClick={() => recorder.current?.stop()}
        >
          <HugeiconsIcon icon={Square01Icon} data-icon="inline-start" />
          {clock(seconds)}
        </InputGroupButton>
      ) : (
        <InputGroupButton
          size="icon-sm"
          aria-label="Record a voice message"
          disabled={disabled || busy}
          onClick={() => void start()}
        >
          {busy ? <Spinner /> : <HugeiconsIcon icon={Mic01Icon} />}
        </InputGroupButton>
      )}
      {error && (
        <span role="alert" className="text-xs text-destructive">
          {error}
        </span>
      )}
      <Dialog
        open={review !== null}
        onOpenChange={(open) => {
          if (!open) discard()
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Recording</DialogTitle>
            <DialogDescription>
              Check the transcript before attaching it.
            </DialogDescription>
          </DialogHeader>
          {review && (
            <>
              <audio
                controls
                src={review.url}
                className="w-full"
                aria-label="Recorded audio"
              />
              <Field>
                <FieldLabel htmlFor="voice-transcript">Transcript</FieldLabel>
                <Textarea
                  id="voice-transcript"
                  rows={4}
                  value={review.text}
                  onChange={(event) =>
                    setReview({ ...review, text: event.target.value })
                  }
                />
              </Field>
              <DialogFooter>
                <Button variant="outline" onClick={discard}>
                  Discard
                </Button>
                <Button
                  disabled={!review.text.trim()}
                  onClick={() => {
                    onReady(review.text.trim(), review.media)
                    discard()
                  }}
                >
                  Attach
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </>
  )
}
