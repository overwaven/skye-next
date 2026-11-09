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

const projectIcons = [
  ["☁️", "Cloud"],
  ["💬", "Chat"],
  ["💻", "Code"],
  ["⚙️", "Settings"],
  ["💼", "Work"],
  ["🎓", "Study"],
  ["❤️", "Health"],
  ["✨", "Sparkles"],
  ["🌍", "World"],
  ["🎨", "Art"],
  ["🧪", "Science"],
  ["🎵", "Music"],
  ["📷", "Camera"],
  ["📁", "Folder"],
  ["💡", "Idea"],
  ["⭐", "Star"],
] as const

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
            ? "This project changed. Close and reopen the editor before saving."
            : (data?.message ?? "The project could not be saved.")
        )
        return
      }
      onCreated((await response.json()) as ProjectRecord)
      setName("")
      setEmoji("☁️")
      setInstructions("")
      onOpenChange(false)
    } catch {
      setError(
        "The project could not be saved. Check your connection and try again."
      )
    } finally {
      setBusy(false)
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{project ? "Edit project" : "New project"}</DialogTitle>
        </DialogHeader>
        <FieldGroup>
          <div className="flex items-end gap-3">
            <Field className="w-20">
              <FieldLabel htmlFor="project-emoji">Icon</FieldLabel>
              <Popover open={iconsOpen} onOpenChange={setIconsOpen}>
                <PopoverTrigger
                  render={
                    <Button
                      id="project-emoji"
                      variant="outline"
                      aria-label="Choose project icon"
                    />
                  }
                >
                  <span aria-hidden="true">{emoji}</span>
                </PopoverTrigger>
                <PopoverContent align="start" className="w-72">
                  <div
                    className="grid grid-cols-4 gap-2"
                    role="group"
                    aria-label="Project icons"
                  >
                    {projectIcons.map(([icon, label]) => (
                      <Button
                        key={icon}
                        variant={emoji === icon ? "secondary" : "ghost"}
                        aria-label={label}
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
              <FieldLabel htmlFor="project-name">Name</FieldLabel>
              <Input
                id="project-name"
                value={name}
                maxLength={64}
                onChange={(event) => setName(event.target.value)}
              />
            </Field>
          </div>
          <Field>
            <FieldLabel htmlFor="project-instructions">Instructions</FieldLabel>
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
            Cancel
          </Button>
          <Button disabled={busy || !name.trim()} onClick={() => void create()}>
            {busy ? (
              <Spinner />
            ) : (
              <HugeiconsIcon icon={Add01Icon} data-icon="inline-start" />
            )}
            {project ? "Save" : "Create"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}
