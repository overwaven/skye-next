"use client"

import * as React from "react"
import { HugeiconsIcon } from "@hugeicons/react"
import { Add01Icon } from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Spinner } from "@/components/ui/spinner"
import { Textarea } from "@/components/ui/textarea"
import type { ProjectRecord } from "@/lib/contracts.generated"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover"
import { useI18n } from "@/components/i18n-provider"
import { translateServerMessage, type MessageKey } from "@/lib/i18n"

const projectIcons = [
  ["☁️", "projectDialog.cloud"],
  ["💬", "projectDialog.chat"],
  ["💻", "projectDialog.code"],
  ["⚙️", "projectDialog.settings"],
  ["💼", "projectDialog.work"],
  ["🎓", "projectDialog.study"],
  ["❤️", "projectDialog.health"],
  ["✨", "projectDialog.sparkles"],
  ["🌍", "projectDialog.world"],
  ["🎨", "projectDialog.art"],
  ["🧪", "projectDialog.science"],
  ["🎵", "projectDialog.music"],
  ["📷", "projectDialog.camera"],
  ["📁", "projectDialog.folder"],
  ["💡", "projectDialog.idea"],
  ["⭐", "projectDialog.star"],
] as const satisfies readonly (readonly [string, MessageKey])[]

export function CreateProjectDialog({
  open,
  onOpenChange,
  csrfToken,
  onCreated,
  project,
}: {
  open: boolean
  onOpenChange: (open: boolean) => void
  csrfToken: string
  onCreated: (project: ProjectRecord) => void
  project?: {
    id: string
    name: string
    emoji?: string
    instructions: string
    revision?: number
  }
}) {
  const { t, locale } = useI18n()
  const [name, setName] = React.useState(project?.name ?? "")
  const [emoji, setEmoji] = React.useState(project?.emoji || "☁️")
  const [instructions, setInstructions] = React.useState(
    project?.instructions ?? ""
  )
  const [iconsOpen, setIconsOpen] = React.useState(false)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState("")

  async function create() {
    setBusy(true)
    setError("")
    try {
      const response = await fetch(
        project
          ? `/api/v1/projects/${encodeURIComponent(project.id)}`
          : "/api/v1/projects",
        {
          method: project ? "PATCH" : "POST",
          headers: {
            "Content-Type": "application/json",
            "X-CSRF-Token": csrfToken,
          },
          body: JSON.stringify({
            name,
            emoji,
            instructions,
            ...(project ? { revision: project.revision } : {}),
          }),
        }
      )
      setBusy(false)
      if (!response.ok) {
        const data = (await response.json().catch(() => null)) as {
          message?: string
        } | null
        setError(
          response.status === 409
            ? t("projectDialog.conflict")
            : data?.message
              ? translateServerMessage(locale, data.message)
              : t("projectDialog.saveFailed")
        )
        return
      }
      onCreated((await response.json()) as ProjectRecord)
      setName("")
      setEmoji("☁️")
      setInstructions("")
      onOpenChange(false)
    } catch {
      setError(t("projectDialog.connection"))
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {project ? t("projectDialog.editTitle") : t("projectDialog.newTitle")}
          </DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <div className="flex items-end gap-3">
            <Field className="w-20">
              <FieldLabel htmlFor="project-emoji">{t("projectDialog.icon")}</FieldLabel>
              <Popover open={iconsOpen} onOpenChange={setIconsOpen}>
                <PopoverTrigger
                  render={
                    <Button
                      id="project-emoji"
                      variant="outline"
                      aria-label={t("projectDialog.chooseIcon")}
                    />
                  }
                >
                  <span aria-hidden="true">{emoji}</span>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-72">
                  <div
                    className="grid grid-cols-4 gap-2"
                    role="group"
                    aria-label={t("projectDialog.icons")}
                  >
                    {projectIcons.map(([icon, labelKey]) => (
                      <Button
                        key={icon}
                        variant={emoji === icon ? "secondary" : "ghost"}
                        aria-label={t(labelKey)}
                        aria-pressed={emoji === icon}
                        onClick={() => {
                          setEmoji(icon)
                          setIconsOpen(false)
                        }}
                      >
                        {icon}
                      </Button>
                    ))}
                  </div>
                </PopoverContent>
              </Popover>
            </Field>
            <Field className="flex-1">
              <FieldLabel htmlFor="project-name">{t("projectDialog.name")}</FieldLabel>
              <Input
                id="project-name"
                value={name}
                maxLength={64}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
          </div>
          <Field>
            <FieldLabel htmlFor="project-instructions">{t("projectDialog.instructions")}</FieldLabel>
            <Textarea
              id="project-instructions"
              value={instructions}
              maxLength={12000}
              rows={4}
              onChange={(event) => setInstructions(event.target.value)}
            />
          </Field>
        </FieldGroup>
        {error && <p className="text-sm text-destructive">{error}</p>}
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            {t("common.cancel")}
          </Button>
          <Button disabled={busy || !name.trim()} onClick={() => void create()}>
            {busy ? (
              <Spinner />
            ) : (
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
            )}
            {project ? t("projectDialog.save") : t("projectDialog.create")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
