"use client"

import * as React from "react"
import { usePathname, useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Archive01Icon,
  ArchiveRestoreIcon,
  Delete02Icon,
  Edit02Icon,
  Folder01Icon,
  MoreHorizontalIcon,
  Tick02Icon,
} from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog"
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuSub,
  DropdownMenuSubContent,
  DropdownMenuSubTrigger,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { Field, FieldGroup, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import type { ThreadRecord } from "@/lib/contracts.generated"

type ListThread = {
  id: string
  title: string
  project_id: string | null
  archived?: boolean
}

export function ThreadMenu({
  thread,
  projects,
  csrfToken,
  onUpdated,
  onDeleted,
}: {
  thread: ListThread
  projects: { id: string; name: string; emoji?: string }[]
  csrfToken: string
  onUpdated?: (thread: ThreadRecord) => void
  onDeleted?: () => void
}) {
  const router = useRouter()
  const pathname = usePathname()
  const [rename, setRename] = React.useState(false)
  const [remove, setRemove] = React.useState(false)
  const [title, setTitle] = React.useState(thread.title)
  const [busy, setBusy] = React.useState(false)
  const [error, setError] = React.useState("")

  async function patch(body: Record<string, unknown>) {
    setBusy(true)
    setError("")
    const response = await fetch(
      `/api/v1/threads/${encodeURIComponent(thread.id)}`,
      {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          "X-CSRF-Token": csrfToken,
        },
        body: JSON.stringify(body),
      }
    )
    setBusy(false)
    if (!response.ok) {
      setError("That change could not be saved.")
      return null
    }
    const updated = (await response.json()) as ThreadRecord
    onUpdated?.(updated)
    router.refresh()
    return updated
  }

  async function removeThread() {
    setBusy(true)
    setError("")
    const response = await fetch(
      `/api/v1/threads/${encodeURIComponent(thread.id)}`,
      { method: "DELETE", headers: { "X-CSRF-Token": csrfToken } }
    )
    setBusy(false)
    if (!response.ok) {
      setError("That thread could not be deleted.")
      return
    }
    setRemove(false)
    onDeleted?.()
    if (pathname === `/chat/${thread.id}`) router.push("/chat")
    router.refresh()
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              aria-label="Thread actions"
              className="row-overflow"
            />
          }
        >
          <HugeiconsIcon icon={MoreHorizontalIcon} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuItem
              onClick={() => {
                setTitle(thread.title)
                setError("")
                setRename(true)
              }}
            >
              <HugeiconsIcon icon={Edit02Icon} />
              Rename
            </DropdownMenuItem>
            <DropdownMenuSub>
              <DropdownMenuSubTrigger>
                <HugeiconsIcon icon={Folder01Icon} />
                Move
              </DropdownMenuSubTrigger>
              <DropdownMenuSubContent>
                <DropdownMenuItem
                  onClick={() => {
                    if (thread.project_id !== null)
                      void patch({ project_id: null })
                  }}
                >
                  <span className="w-4 text-center">–</span>
                  No project
                  {thread.project_id === null && (
                    <HugeiconsIcon icon={Tick02Icon} className="ms-auto" />
                  )}
                </DropdownMenuItem>
                {projects.map((project) => (
                  <DropdownMenuItem
                    key={project.id}
                    onClick={() => {
                      if (thread.project_id !== project.id)
                        void patch({ project_id: project.id })
                    }}
                  >
                    <span aria-hidden="true">{project.emoji || "📁"}</span>
                    <span className="truncate">{project.name}</span>
                    {thread.project_id === project.id && (
                      <HugeiconsIcon icon={Tick02Icon} className="ms-auto" />
                    )}
                  </DropdownMenuItem>
                ))}
              </DropdownMenuSubContent>
            </DropdownMenuSub>
            <DropdownMenuItem
              onClick={() => {
                void patch({ archived: !thread.archived })
              }}
            >
              <HugeiconsIcon
                icon={thread.archived ? ArchiveRestoreIcon : Archive01Icon}
              />
              {thread.archived ? "Unarchive" : "Archive"}
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem
              variant="destructive"
              onClick={() => {
                setError("")
                setRemove(true)
              }}
            >
              <HugeiconsIcon icon={Delete02Icon} />
              Delete
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      <Dialog open={rename} onOpenChange={setRename}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Rename</DialogTitle>
          </DialogHeader>
          <FieldGroup>
            <Field>
              <FieldLabel htmlFor={`thread-title-${thread.id}`}>
                Title
              </FieldLabel>
              <Input
                id={`thread-title-${thread.id}`}
                value={title}
                maxLength={128}
                onChange={(event) => setTitle(event.target.value)}
              />
            </Field>
          </FieldGroup>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <DialogFooter>
            <Button variant="outline" onClick={() => setRename(false)}>
              Cancel
            </Button>
            <Button
              disabled={busy || !title.trim()}
              onClick={() => {
                void patch({ title }).then((updated) => {
                  if (updated) setRename(false)
                })
              }}
            >
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
      <AlertDialog open={remove} onOpenChange={setRemove}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this thread?</AlertDialogTitle>
            <AlertDialogDescription>
              Its messages, runs and activity will be removed. This cannot be
              undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={busy}
              onClick={(event) => {
                event.preventDefault()
                void removeThread()
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
