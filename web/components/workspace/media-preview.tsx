"use client"
/* eslint-disable @next/next/no-img-element -- authenticated opaque media URLs */

import { Dialog as DialogPrimitive } from "@base-ui/react/dialog"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Cancel01Icon,
  Download01Icon,
  File01Icon,
} from "@hugeicons/core-free-icons"
import {
  Dialog,
  DialogPortal,
  DialogTitle,
  DialogClose,
} from "@/components/ui/dialog"
import { Button } from "@/components/ui/button"
import { useState } from "react"
import { useI18n } from "@/components/i18n-provider"

export function MediaPreview({
  open,
  onOpenChange,
  name,
  mediaType,
  src,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  name: string
  mediaType: string
  src?: string
}) {
  const { t } = useI18n()
  const [failed, setFailed] = useState(false)
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogPortal>
        <DialogPrimitive.Backdrop className="media-preview-backdrop" />
        <DialogPrimitive.Popup
          className="media-preview"
          data-slot="media-preview"
        >
          <header className="media-preview-header">
            <DialogTitle className="min-w-0 flex-1 truncate">
              {name}
            </DialogTitle>
            {src && (
              <Button
                variant="ghost"
                nativeButton={false}
                render={<a href={src} download={name} />}
                aria-label={`${t("media.download")} ${name}`}
              >
                <HugeiconsIcon icon={Download01Icon} data-icon="inline-start" />
                <span className="hidden sm:inline">{t("media.download")}</span>
              </Button>
            )}
            <DialogClose
              render={
                <Button
                  variant="ghost"
                  size="icon"
                  aria-label={t("media.closePreview")}
                />
              }
            >
              <HugeiconsIcon icon={Cancel01Icon} />
            </DialogClose>
          </header>
          <div className="media-preview-stage">
            {src && !failed && mediaType.startsWith("image/") ? (
              <img src={src} alt={name} onError={() => setFailed(true)} />
            ) : src && !failed && mediaType.startsWith("audio/") ? (
              <audio
                src={src}
                controls
                aria-label={name}
                onError={() => setFailed(true)}
              />
            ) : (
              <div className="flex flex-col items-center gap-4">
                <HugeiconsIcon icon={File01Icon} />
                <p>
                  {failed || !src
                    ? t("media.noLongerAvailable")
                    : t("media.noPreview")}
                </p>
              </div>
            )}
          </div>
        </DialogPrimitive.Popup>
      </DialogPortal>
    </Dialog>
  )
}
