"use client"
/* eslint-disable @next/next/no-img-element -- opaque same-origin media */

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Download01Icon,
  EyeIcon,
  File01Icon,
  GridViewIcon,
  Image01Icon,
  ListViewIcon,
  MoreHorizontalIcon,
  MusicNote01Icon,
  Search01Icon,
  Tick02Icon,
  Upload01Icon,
} from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  Attachment,
  AttachmentActions,
  AttachmentContent,
  AttachmentDescription,
  AttachmentMedia,
  AttachmentTitle,
  AttachmentTrigger,
} from "@/components/ui/attachment"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import type { MediaRecord } from "@/lib/contracts.generated"
import { MediaPreview } from "@/components/workspace/media-preview"
import { Separator } from "@/components/ui/separator"
import { cn } from "@/lib/utils"

type Upload = {
  key: string
  name: string
  progress: number
}

type Filter = "all" | "images" | "files" | "audio"

function sizeLabel(size: number) {
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

function audio(media: MediaRecord) {
  return media.media_type.startsWith("audio/")
}

function matches(media: MediaRecord, filter: Filter) {
  if (filter === "images") return media.is_image
  if (filter === "audio") return audio(media)
  if (filter === "files") return !media.is_image && !audio(media)
  return true
}

export function MediaPicker({
  open,
  onOpenChange,
  csrfToken,
  selected,
  onToggle,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  csrfToken: string
  selected: MediaRecord[]
  onToggle: (media: MediaRecord) => void
}) {
  const [items, setItems] = React.useState<MediaRecord[]>([])
  const [loading, setLoading] = React.useState(false)
  const [uploading, setUploading] = React.useState<Upload[]>([])
  const [error, setError] = React.useState("")
  const [query, setQuery] = React.useState("")
  const [filter, setFilter] = React.useState<Filter>("all")
  const [view, setView] = React.useState<"grid" | "list">("grid")
  const [preview, setPreview] = React.useState<MediaRecord | null>(null)
  const input = React.useRef<HTMLInputElement>(null)
  const requests = React.useRef(new Map<string, XMLHttpRequest>())

  React.useEffect(() => {
    if (!open) return
    let cancelled = false
    // Opening the dialog starts a fetch; this is external-store synchronisation.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setLoading(true)
    setError("")
    fetch("/api/v1/media", { cache: "no-store" })
      .then(async (response) => {
        if (!response.ok) throw new Error("The library is unavailable.")
        const data = (await response.json()) as { media: MediaRecord[] }
        if (!cancelled)
          setItems((current) => {
            const byId = new Map(
              [...data.media, ...current].map((item) => [item.id, item])
            )
            return [...byId.values()].sort(
              (left, right) => right.created_at - left.created_at
            )
          })
      })
      .catch(() => {
        if (!cancelled) setError("The library is unavailable.")
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [open])

  function upload(file: File) {
    const key = `${file.name}:${file.size}:${Date.now()}`
    setUploading((current) => [
      ...current,
      { key, name: file.name, progress: 0 },
    ])
    setError("")
    const request = new XMLHttpRequest()
    requests.current.set(key, request)
    request.open("POST", "/api/v1/media")
    request.setRequestHeader("X-CSRF-Token", csrfToken)
    request.setRequestHeader("X-Skye-File-Name", file.name)
    request.setRequestHeader(
      "Content-Type",
      file.type || "application/octet-stream"
    )
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return
      const progress = Math.round((event.loaded / event.total) * 100)
      setUploading((current) =>
        current.map((item) => (item.key === key ? { ...item, progress } : item))
      )
    }
    request.onload = () => {
      requests.current.delete(key)
      setUploading((current) => current.filter((item) => item.key !== key))
      if (request.status === 201) {
        const media = JSON.parse(request.responseText) as MediaRecord
        setItems((current) => [media, ...current])
        onToggle(media)
      } else {
        setError("That file could not be attached.")
      }
    }
    request.onerror = () => {
      requests.current.delete(key)
      setUploading((current) => current.filter((item) => item.key !== key))
      setError("The upload was interrupted. Try again.")
    }
    request.send(file)
  }

  async function remove(media: MediaRecord) {
    const response = await fetch(
      `/api/v1/media/${encodeURIComponent(media.id)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": csrfToken } }
    )
    if (!response.ok) {
      setError("That file could not be removed.")
      return
    }
    setItems((current) => current.filter((item) => item.id !== media.id))
    if (selected.some((item) => item.id === media.id)) onToggle(media)
  }

  const visible = items.filter(
    (media) =>
      matches(media, filter) &&
      media.name.toLowerCase().includes(query.trim().toLowerCase())
  )

  function trigger(media: MediaRecord) {
    const picked = selected.some((item) => item.id === media.id)
    return (
      <Attachment
        orientation={view === "grid" ? "vertical" : "horizontal"}
        className={cn("library-attachment", picked && "is-selected")}
        presentation="library"
      >
        <AttachmentTrigger
          aria-label={
            media.availability === "expired"
              ? `${media.name} has expired`
              : `${picked ? "Remove" : "Attach"} ${media.name}`
          }
          disabled={media.availability === "expired"}
          onClick={() => onToggle(media)}
        />
        <AttachmentMedia variant={media.is_image ? "image" : "icon"}>
          {media.is_image ? (
            <img
              src={`/api/v1/media/${encodeURIComponent(media.id)}`}
              alt=""
              loading="lazy"
            />
          ) : audio(media) ? (
            <HugeiconsIcon icon={MusicNote01Icon} />
          ) : (
            <HugeiconsIcon icon={File01Icon} />
          )}
        </AttachmentMedia>
        <AttachmentContent>
          <AttachmentTitle>{media.name}</AttachmentTitle>
          <AttachmentDescription>
            {media.availability === "expired"
              ? "Expired"
              : audio(media)
                ? "Audio"
                : media.is_image
                  ? "Image"
                  : "Document"}
          </AttachmentDescription>
        </AttachmentContent>
        <span className="media-size">{sizeLabel(media.size)}</span>
        <AttachmentActions>
          {picked && (
            <span className="flex size-6 items-center justify-center rounded-full bg-primary text-primary-foreground">
              <HugeiconsIcon icon={Tick02Icon} className="size-3.5" />
            </span>
          )}
          <DropdownMenu>
            <DropdownMenuTrigger
              render={
                <Button
                  variant="ghost"
                  size="icon-sm"
                  aria-label={`Actions for ${media.name}`}
                />
              }
            >
              <HugeiconsIcon icon={MoreHorizontalIcon} />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              <DropdownMenuGroup>
                <DropdownMenuItem onClick={() => setPreview(media)}>
                  <HugeiconsIcon icon={EyeIcon} />
                  Preview
                </DropdownMenuItem>
                {media.availability === "available" && (
                  <DropdownMenuItem
                    render={
                      <a
                        href={`/api/v1/media/${encodeURIComponent(media.id)}`}
                        download={media.name}
                      />
                    }
                  >
                    <HugeiconsIcon icon={Download01Icon} />
                    Download
                  </DropdownMenuItem>
                )}
              </DropdownMenuGroup>
              <DropdownMenuSeparator />
              <DropdownMenuGroup>
                <DropdownMenuItem
                  variant="destructive"
                  onClick={() => void remove(media)}
                >
                  <HugeiconsIcon icon={Delete02Icon} />
                  Delete
                </DropdownMenuItem>
              </DropdownMenuGroup>
            </DropdownMenuContent>
          </DropdownMenu>
        </AttachmentActions>
      </Attachment>
    )
  }

  return (
    <>
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent className="max-h-[85dvh] sm:max-w-3xl">
          <DialogHeader>
            <DialogTitle>Files</DialogTitle>
            <DialogDescription className="sr-only">
              Attach a saved file or upload a new one.
            </DialogDescription>
          </DialogHeader>
          <div className="media-toolbar">
            <Button variant="outline" onClick={() => input.current?.click()}>
              <HugeiconsIcon icon={Upload01Icon} data-icon="inline-start" />
              Upload
            </Button>
            <input
              ref={input}
              type="file"
              multiple
              className="sr-only"
              onChange={(event) => {
                for (const file of Array.from(event.target.files ?? []))
                  upload(file)
                event.target.value = ""
              }}
            />
            <div className="relative min-w-40 flex-1">
              <HugeiconsIcon
                icon={Search01Icon}
                className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
              />
              <Input
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Search files"
                aria-label="Search files"
                className="ps-9"
              />
            </div>
            <ToggleGroup
              value={[filter]}
              onValueChange={(value) =>
                setFilter((value[0] as Filter) ?? "all")
              }
              aria-label="File type"
            >
              <ToggleGroupItem value="all">All</ToggleGroupItem>
              <ToggleGroupItem value="images" aria-label="Images">
                <HugeiconsIcon icon={Image01Icon} />
              </ToggleGroupItem>
              <ToggleGroupItem value="audio" aria-label="Audio">
                <HugeiconsIcon icon={MusicNote01Icon} />
              </ToggleGroupItem>
              <ToggleGroupItem value="files" aria-label="Documents">
                <HugeiconsIcon icon={File01Icon} />
              </ToggleGroupItem>
            </ToggleGroup>
            <Separator
              orientation="vertical"
              className="media-toolbar-separator"
            />
            <ToggleGroup
              value={[view]}
              onValueChange={(value) =>
                setView((value[0] as "grid" | "list") ?? "grid")
              }
              aria-label="Layout"
            >
              <ToggleGroupItem value="grid" aria-label="Grid view">
                <HugeiconsIcon icon={GridViewIcon} />
              </ToggleGroupItem>
              <ToggleGroupItem value="list" aria-label="List view">
                <HugeiconsIcon icon={ListViewIcon} />
              </ToggleGroupItem>
            </ToggleGroup>
          </div>
          {uploading.length > 0 && (
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Spinner />
              {uploading[0].name} · {uploading[0].progress}%
              <Button
                variant="ghost"
                size="sm"
                onClick={() => {
                  const request = requests.current.get(uploading[0].key)
                  request?.abort()
                  requests.current.delete(uploading[0].key)
                  setUploading((current) => current.slice(1))
                }}
              >
                Cancel
              </Button>
            </div>
          )}
          {error && <p className="text-sm text-destructive">{error}</p>}
          {loading ? (
            <div className="flex justify-center py-10">
              <Spinner />
            </div>
          ) : visible.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">
              {query || filter !== "all" ? "No matches." : "Nothing saved yet."}
            </p>
          ) : view === "grid" ? (
            <div className="media-grid">
              {visible.map((media) => (
                <React.Fragment key={media.id}>{trigger(media)}</React.Fragment>
              ))}
            </div>
          ) : (
            <ul className="media-list">
              <li className="media-list-head" aria-hidden="true">
                <span>Name</span>
                <span>Type</span>
                <span>Size</span>
                <span />
              </li>
              {visible.map((media) => (
                <li key={media.id}>{trigger(media)}</li>
              ))}
            </ul>
          )}
        </DialogContent>
      </Dialog>
      {preview && (
        <MediaPreview
          key={preview.id}
          open={preview !== null}
          onOpenChange={(next) => {
            if (!next) setPreview(null)
          }}
          name={preview.name}
          mediaType={preview.media_type}
          src={
            preview.availability === "expired"
              ? undefined
              : `/api/v1/media/${encodeURIComponent(preview.id)}`
          }
        />
      )}
    </>
  )
}
