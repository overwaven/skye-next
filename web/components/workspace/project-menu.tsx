"use client"

import { useState } from "react"
import { usePathname, useRouter } from "next/navigation"
import { HugeiconsIcon } from "@hugeicons/react"
import {
  Delete02Icon,
  Edit02Icon,
  MoreHorizontalIcon,
} from "@hugeicons/core-free-icons"
import { Button } from "@/components/ui/button"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  AlertDialog,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog"
import { Spinner } from "@/components/ui/spinner"
import { toast } from "@/components/ui/toast"
import { CreateProjectDialog } from "@/components/workspace/create-project-dialog"
import type { NavigationData } from "@/lib/foundation"

export function ProjectMenu({
  project,
  csrfToken,
}: {
  project: NavigationData["projects"][number]
  csrfToken: string
}) {
  const [editing, setEditing] = useState(false)
  const [removing, setRemoving] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState("")
  const router = useRouter()
  const pathname = usePathname()

  async function removeProject() {
    setBusy(true)
    setError("")
    try {
      const response = await fetch(
        `/api/v1/projects/${encodeURIComponent(project.id)}`,
        {
          method: "DELETE",
          headers: { "X-CSRF-Token": csrfToken },
        }
      )
      if (!response.ok) {
        setError("That project could not be deleted.")
        return
      }
      setRemoving(false)
      toast.add({
        title: "Project deleted",
        description: "Its threads are still here, now without a project.",
        type: "success",
      })
      if (pathname === `/projects/${project.id}`) router.push("/chat")
      router.refresh()
    } catch {
      setError("That project could not be deleted. Check your connection.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <DropdownMenu>
        <DropdownMenuTrigger
          render={
            <Button
              variant="ghost"
              size="icon-sm"
              className="row-overflow"
              aria-label={`Actions for ${project.name}`}
            />
          }
        >
          <HugeiconsIcon icon={MoreHorizontalIcon} />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuGroup>
            <DropdownMenuItem onClick={() => setEditing(true)}>
              <HugeiconsIcon icon={Edit02Icon} />
              Edit project
            </DropdownMenuItem>
          </DropdownMenuGroup>
          <DropdownMenuSeparator />
          <DropdownMenuGroup>
            <DropdownMenuItem
              variant="destructive"
              onClick={() => {
                setError("")
                setRemoving(true)
              }}
            >
              <HugeiconsIcon icon={Delete02Icon} />
              Delete project
            </DropdownMenuItem>
          </DropdownMenuGroup>
        </DropdownMenuContent>
      </DropdownMenu>
      {editing && (
        <CreateProjectDialog
          key={`${project.id}:${project.revision}`}
          project={project}
          open={editing}
          onOpenChange={setEditing}
          csrfToken={csrfToken}
          onCreated={() => router.refresh()}
        />
      )}
      <AlertDialog
        open={removing}
        onOpenChange={(open) => {
          if (!open && !busy) setRemoving(false)
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {project.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              The project and its instructions are removed. Its threads stay
              and move to No project.
            </AlertDialogDescription>
          </AlertDialogHeader>
          {error && <p className="text-sm text-destructive">{error}</p>}
          <AlertDialogFooter>
            <AlertDialogCancel disabled={busy}>Cancel</AlertDialogCancel>
            <Button
              variant="destructive"
              disabled={busy}
              onClick={() => void removeProject()}
            >
              {busy && <Spinner data-icon="inline-start" />}
              Delete project
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </>
  )
}
