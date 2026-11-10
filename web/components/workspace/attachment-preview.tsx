"use client"
/* eslint-disable @next/next/no-img-element -- opaque same-origin media */

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Cancel01Icon,
  EyeIcon,
  File01Icon,
  MusicNote01Icon,
} from "@hugeicons/core-free-icons"
import {
  Attachment,
  AttachmentAction,
  AttachmentActions,
  AttachmentContent,
  AttachmentDescription,
  AttachmentMedia,
  AttachmentTitle,
  AttachmentTrigger,
} from "@/components/ui/attachment"
import { MediaPreview } from "@/components/workspace/media-preview"
import { useI18n } from "@/components/i18n-provider"

function sizeLabel(size?: number) {
  if (size === undefined) return ""
  if (size < 1024) return `${size} B`
  if (size < 1024 * 1024) return `${Math.max(1, Math.round(size / 1024))} KB`
  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function PreviewableAttachment({
  name,
  mediaType,
  size,
  src,
  availability,
  onRemove,
}: {
  name: string
  mediaType: string
  size?: number
  src?: string
  availability: "available" | "expired" | "unresolved"
  onRemove?: () => void
}) {
  const { t } = useI18n()
  const [open, setOpen] = React.useState(false)
  const [broken, setBroken] = React.useState(false)
  const available = availability === "available" && Boolean(src) && !broken
  const image = available && mediaType.startsWith("image/")
  const audio = available && mediaType.startsWith("audio/")
  return (
    <>
      <Attachment
        size="sm"
        state={
          availability === "expired" || availability === "unresolved"
            ? "error"
            : "done"
        }
      >
        {available && (
          <AttachmentTrigger
            aria-label={t("media.previewFile", { name })}
            onClick={() => setOpen(true)}
          />
        )}
        <AttachmentMedia variant={image ? "image" : "icon"}>
          {image ? (
            <img
              src={src}
              alt=""
              loading="lazy"
              onError={() => setBroken(true)}
            />
          ) : audio ? (
            <HugeiconsIcon icon={MusicNote01Icon} />
          ) : (
            <HugeiconsIcon icon={File01Icon} />
          )}
        </AttachmentMedia>
        <AttachmentContent>
          <AttachmentTitle>{name}</AttachmentTitle>
          <AttachmentDescription>
            {broken
              ? t("media.noLongerAvailable")
              : availability === "expired"
                ? t("media.expired")
                : availability === "unresolved"
                  ? t("media.notAvailableHere")
                  : [mediaType, sizeLabel(size)].filter(Boolean).join(" · ")}
          </AttachmentDescription>
        </AttachmentContent>
        <AttachmentActions>
          {onRemove ? (
            <AttachmentAction aria-label={t("media.removeFile", { name })} onClick={onRemove}>
              <HugeiconsIcon icon={Cancel01Icon} />
            </AttachmentAction>
          ) : (
            <AttachmentAction
              aria-label={t("media.previewFile", { name })}
              disabled={!available}
              onClick={() => setOpen(true)}
            >
              <HugeiconsIcon icon={EyeIcon} />
            </AttachmentAction>
          )}
        </AttachmentActions>
      </Attachment>
      <MediaPreview
        open={open}
        onOpenChange={setOpen}
        name={name}
        mediaType={mediaType}
        src={available ? src : undefined}
      />
    </>
  )
}
